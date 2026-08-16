from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from . import scheduler as core
from .buffer_client import BufferAPIError
from .scheduler import Execution, SocialScheduler as BaseSocialScheduler
from .truth_status import queue_slo

core.CONSUMED_STATUSES = {"scheduled", "sending", "sent", "error"}


class SocialScheduler(BaseSocialScheduler):
    """Production Buffer executor with conservative error handling and explicit fill SLO truth."""

    def _future_target(self, ex: Execution, now: datetime) -> datetime | None:
        if self.settings.get("content_source") == "socialmarket_outbox":
            return ex.target_at if ex.target_at > now + timedelta(minutes=2) else None
        return super()._future_target(ex, now)

    def _post_input(self, ex: Execution, due_at: datetime) -> dict[str, Any]:
        data = super()._post_input(ex, due_at)
        if self.settings.get("content_source") == "socialmarket_outbox":
            data["source"] = f"socialmarket:{ex.campaign_id}:{ex.service}"
        return data

    @staticmethod
    def _consumed_rank(post: dict[str, Any]) -> int:
        return {"sent": 4, "sending": 3, "scheduled": 2, "error": 1}.get(str(post.get("status")), 0)

    def reconcile_and_fill(self, executions: list[Execution], posts: list[dict[str, Any]]) -> None:
        for post in posts:
            if post.get("status") == "error":
                self.actions.append({
                    "type": "existing_error_blocked",
                    "postId": post.get("id"),
                    "channelId": post.get("channelId"),
                    "ideaId": post.get("ideaId"),
                    "reason": "manual_or_classified_recovery_required_before_retry",
                })

        if self.settings.get("content_source") != "socialmarket_outbox":
            super().reconcile_and_fill(executions, posts)
            return

        consumed_by_key: dict[tuple[str, str], dict[str, Any]] = {}
        for post in posts:
            if post.get("status") not in core.CONSUMED_STATUSES:
                continue
            key = self._post_key(post)
            existing = consumed_by_key.get(key)
            if existing is None or self._consumed_rank(post) > self._consumed_rank(existing):
                consumed_by_key[key] = post

        remaining: list[Execution] = []
        for ex in executions:
            existing = consumed_by_key.get(self._execution_key(ex))
            if not existing:
                remaining.append(ex)
                continue
            status = existing.get("status")
            common = {
                "campaign": ex.campaign_id,
                "service": ex.service,
                "postId": existing.get("id"),
                "dueAt": existing.get("dueAt"),
                "sentAt": existing.get("sentAt"),
            }
            if status == "sent":
                self.actions.append({"type": "already_published", **common})
            elif status == "error":
                self.actions.append({"type": "already_error", **common, "reason": "buffer_status_error"})
            else:
                self.actions.append({"type": "already_scheduled", **common})

        super().reconcile_and_fill(remaining, posts)

    def run(self) -> dict[str, Any]:
        org_id = self.settings["organization_id"]
        account = self.client.account()
        org_ids = {org["id"] for org in account.get("organizations", [])}
        if org_id not in org_ids:
            raise BufferAPIError(f"Configured organization {org_id} is not accessible")

        live_channels = {c["id"]: c for c in self.client.channels(org_id)}
        missing = [meta["id"] for meta in self.channels.values() if meta["id"] not in live_channels]
        if missing:
            raise BufferAPIError(f"Configured Buffer channels are missing/disconnected: {missing}")

        posts = self.client.posts(org_id, core.STATUS_READ_SET)
        initial_active = sum(1 for p in posts if p.get("status") in core.ACTIVE_QUEUE_STATUSES)
        executions = self.expand()

        if self.settings.get("content_source") == "socialmarket_outbox":
            ideas: list[dict[str, Any]] = []
            self.actions.append({"type": "content_source", "source": "socialmarket_outbox", "executions": len(executions)})
        else:
            ideas = self.client.ideas(org_id)
            self.ensure_ideas(executions, ideas)

        self.reconcile_and_fill(executions, posts)
        scheduled_created = sum(1 for action in self.actions if action.get("type") == "scheduled")
        would_schedule = sum(1 for action in self.actions if action.get("type") == "would_schedule")

        # Full truth: after live writes, re-read Buffer only when this run created posts.
        # This avoids reporting the pre-write queue as if it were the final state.
        final_posts = posts
        if self.mode == "live" and scheduled_created > 0:
            final_posts = self.client.posts(org_id, core.STATUS_READ_SET)

        observed_active = sum(1 for p in final_posts if p.get("status") in core.ACTIVE_QUEUE_STATUSES)
        effective_active = observed_active if self.mode == "live" else min(
            int(self.settings["queue_limit"]), initial_active + would_schedule
        )
        slo = queue_slo(effective_active, int(self.settings["queue_limit"]))

        if not slo["met"]:
            self.actions.append({
                "type": "queue_underfilled",
                "severity": "CRITICAL",
                "active": slo["active_queue"],
                "limit": slo["queue_limit"],
                "missing_slots": slo["missing_slots"],
                "reason": "approved_supply_or_execution_shortage",
            })

        status_counts = Counter(str(p.get("status") or "unknown") for p in final_posts)
        channel_service = {meta["id"]: service for service, meta in self.channels.items()}
        next_scheduled = sorted(
            [
                {
                    "id": p.get("id"),
                    "status": p.get("status"),
                    "channelId": p.get("channelId"),
                    "service": channel_service.get(p.get("channelId"), "unknown"),
                    "dueAt": p.get("dueAt"),
                }
                for p in final_posts if p.get("status") in core.ACTIVE_QUEUE_STATUSES
            ],
            key=lambda row: str(row.get("dueAt") or ""),
        )

        return {
            "mode": self.mode,
            "organization": org_id,
            "timezone": self.settings["timezone"],
            "content_source": self.settings.get("content_source", "legacy_backlog"),
            "posts_seen": len(final_posts),
            "ideas_seen": len(ideas),
            "active_queue": slo["active_queue"],
            "queue_limit": slo["queue_limit"],
            "queue_slo": slo,
            "initial_active_queue": initial_active,
            "scheduled_created": scheduled_created,
            "post_write_status_counts": dict(status_counts),
            "next_scheduled": next_scheduled,
            "buffer_posts": [
                {"id": p.get("id"), "status": p.get("status"), "dueAt": p.get("dueAt"), "sentAt": p.get("sentAt")}
                for p in final_posts if p.get("id")
            ],
            "actions": self.actions,
        }
