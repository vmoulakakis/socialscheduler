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
    """Production Buffer executor with per-channel capacity and explicit full-truth SLO reporting."""

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

    def _active_by_service(self, posts: list[dict[str, Any]]) -> dict[str, int]:
        return {
            service: sum(
                1 for post in posts
                if post.get("status") in core.ACTIVE_QUEUE_STATUSES and post.get("channelId") == meta["id"]
            )
            for service, meta in self.channels.items()
        }

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

        # Buffer capacity is per connected channel, not global. Reuse the proven
        # core reconciler independently for each channel so no platform can consume
        # another platform's ten scheduled-post slots.
        per_channel_limit = int(self.settings.get("queue_limit_per_channel", self.settings.get("queue_limit", 10)))
        original_queue_limit = self.settings.get("queue_limit", 10)
        original_max_creates = self.settings.get("max_creates_per_run", 10)
        try:
            self.settings["queue_limit"] = per_channel_limit
            self.settings["max_creates_per_run"] = per_channel_limit
            for service, meta in self.channels.items():
                channel_id = meta["id"]
                channel_posts = [post for post in posts if post.get("channelId") == channel_id]
                channel_execs = [ex for ex in remaining if ex.service == service]
                action_start = len(self.actions)
                super().reconcile_and_fill(channel_execs, channel_posts)
                for action in self.actions[action_start:]:
                    action.setdefault("service", service)
                    action.setdefault("channelId", channel_id)
        finally:
            self.settings["queue_limit"] = original_queue_limit
            self.settings["max_creates_per_run"] = original_max_creates

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
        initial_by_service = self._active_by_service(posts)
        executions = self.expand()

        if self.settings.get("content_source") == "socialmarket_outbox":
            ideas: list[dict[str, Any]] = []
            self.actions.append({"type": "content_source", "source": "socialmarket_outbox", "executions": len(executions)})
        else:
            ideas = self.client.ideas(org_id)
            self.ensure_ideas(executions, ideas)

        self.reconcile_and_fill(executions, posts)
        scheduled_created = sum(1 for action in self.actions if action.get("type") == "scheduled")

        # Re-read after writes so the dashboard/email reports Buffer truth after this run.
        final_posts = posts
        if self.mode == "live" and scheduled_created > 0:
            final_posts = self.client.posts(org_id, core.STATUS_READ_SET)

        observed_by_service = self._active_by_service(final_posts)
        per_channel_limit = int(self.settings.get("queue_limit_per_channel", self.settings.get("queue_limit", 10)))
        channel_slo: dict[str, dict[str, Any]] = {}
        for service in self.channels:
            if self.mode == "live":
                effective = observed_by_service.get(service, 0)
            else:
                predicted = sum(
                    1 for action in self.actions
                    if action.get("type") == "would_schedule" and action.get("service") == service
                )
                effective = min(per_channel_limit, initial_by_service.get(service, 0) + predicted)
            channel_slo[service] = queue_slo(effective, per_channel_limit)
            if not channel_slo[service]["met"]:
                self.actions.append({
                    "type": "queue_underfilled",
                    "severity": "CRITICAL",
                    "service": service,
                    "channelId": self.channels[service]["id"],
                    "active": channel_slo[service]["active_queue"],
                    "limit": per_channel_limit,
                    "missing_slots": channel_slo[service]["missing_slots"],
                    "reason": "approved_supply_or_execution_shortage",
                })

        total_active = sum(item["active_queue"] for item in channel_slo.values())
        total_limit = per_channel_limit * len(channel_slo)
        slo = queue_slo(total_active, total_limit)
        slo["met"] = all(item["met"] for item in channel_slo.values())
        slo["severity"] = "OK" if slo["met"] else "CRITICAL"

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
            "queue_limit_per_channel": per_channel_limit,
            "queue_slo": slo,
            "channel_queue_slo": channel_slo,
            "initial_active_queue": sum(initial_by_service.values()),
            "initial_active_by_service": initial_by_service,
            "scheduled_created": scheduled_created,
            "post_write_status_counts": dict(status_counts),
            "next_scheduled": next_scheduled,
            "buffer_posts": [
                {"id": p.get("id"), "status": p.get("status"), "channelId": p.get("channelId"), "dueAt": p.get("dueAt"), "sentAt": p.get("sentAt")}
                for p in final_posts if p.get("id")
            ],
            "actions": self.actions,
        }
