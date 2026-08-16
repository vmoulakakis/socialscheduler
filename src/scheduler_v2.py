from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from . import scheduler as core
from .buffer_client import BufferAPIError
from .scheduler import Execution, SocialScheduler as BaseSocialScheduler

core.CONSUMED_STATUSES = {"scheduled", "sending", "sent", "error"}


class SocialScheduler(BaseSocialScheduler):
    """Production Buffer executor with per-channel Free-plan capacity guards."""

    runtime_snapshot: dict[str, Any] | None = None

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
        if self.settings.get("content_source") != "socialmarket_outbox":
            super().reconcile_and_fill(executions, posts)
            return

        now = self.now()
        active = [p for p in posts if p.get("status") in core.ACTIVE_QUEUE_STATUSES]
        active_by_channel = Counter(str(p.get("channelId") or "") for p in active)
        per_channel_limit = int(self.settings.get("queue_limit_per_channel", self.settings.get("queue_limit", 10)))
        slots_by_channel = {
            meta["id"]: max(0, per_channel_limit - int(active_by_channel.get(meta["id"], 0)))
            for meta in self.channels.values()
        }

        consumed_by_key: dict[tuple[str, str], dict[str, Any]] = {}
        for post in posts:
            if post.get("status") not in core.CONSUMED_STATUSES:
                continue
            key = self._post_key(post)
            existing = consumed_by_key.get(key)
            if existing is None or self._consumed_rank(post) > self._consumed_rank(existing):
                consumed_by_key[key] = post
            if post.get("status") == "error":
                self.actions.append({
                    "type": "existing_error_blocked",
                    "postId": post.get("id"),
                    "channelId": post.get("channelId"),
                    "ideaId": post.get("ideaId"),
                    "reason": "manual_or_classified_recovery_required_before_retry",
                })

        candidates: list[Execution] = []
        for ex in executions:
            if ex.hold:
                self.actions.append({"type": "hold", "campaign": ex.campaign_id, "service": ex.service})
                continue
            if ex.requires_verification:
                self.actions.append({"type": "blocked", "campaign": ex.campaign_id, "service": ex.service, "reason": "fresh_verification_required"})
                continue
            existing = consumed_by_key.get(self._execution_key(ex))
            if existing:
                common = {
                    "campaign": ex.campaign_id,
                    "service": ex.service,
                    "postId": existing.get("id"),
                    "dueAt": existing.get("dueAt"),
                    "sentAt": existing.get("sentAt"),
                }
                status = existing.get("status")
                if status == "sent":
                    self.actions.append({"type": "already_published", **common})
                elif status == "error":
                    self.actions.append({"type": "already_error", **common, "reason": "buffer_status_error"})
                else:
                    self.actions.append({"type": "already_scheduled", **common})
                continue
            target = self._future_target(ex, now)
            if not target:
                self.actions.append({"type": "skip_late", "campaign": ex.campaign_id, "service": ex.service, "reason": "scheduled_time_elapsed"})
                continue
            if ex.service in core.MEDIA_REQUIRED:
                if not ex.media_url or not self._url_works(ex.media_url):
                    self.actions.append({"type": "blocked", "campaign": ex.campaign_id, "service": ex.service, "reason": "media_unavailable"})
                    continue
            candidates.append(ex)

        max_creates = int(self.settings.get("max_creates_per_run", 30))
        creates = 0
        for ex in self._fair_order(candidates):
            if creates >= max_creates:
                break
            if slots_by_channel.get(ex.channel_id, 0) <= 0:
                continue
            due_at = self._future_target(ex, now)
            if due_at is None:
                continue
            input_data = self._post_input(ex, due_at)
            if input_data["mode"] != "customScheduled":
                raise RuntimeError("Safety invariant violated: only customScheduled is allowed")
            if due_at <= now:
                raise RuntimeError("Safety invariant violated: dueAt must be in the future")
            if self.mode == "live":
                created = self.client.create_post(input_data)
                self.actions.append({
                    "type": "scheduled",
                    "campaign": ex.campaign_id,
                    "service": ex.service,
                    "dueAt": created.get("dueAt"),
                    "postId": created.get("id"),
                })
            else:
                self.actions.append({"type": "would_schedule", "campaign": ex.campaign_id, "service": ex.service, "dueAt": core.iso_seconds(due_at)})
            slots_by_channel[ex.channel_id] -= 1
            creates += 1

        for service, meta in self.channels.items():
            channel_id = meta["id"]
            if slots_by_channel.get(channel_id, 0) == 0:
                self.actions.append({
                    "type": "channel_queue_full",
                    "service": service,
                    "channelId": channel_id,
                    "active": per_channel_limit,
                    "limit": per_channel_limit,
                })

    def run(self) -> dict[str, Any]:
        org_id = self.settings["organization_id"]
        snapshot = self.runtime_snapshot or self.client.runtime_snapshot(org_id)
        account = snapshot.get("account") or {}
        org_ids = {org["id"] for org in account.get("organizations", [])}
        if org_id not in org_ids:
            raise BufferAPIError(f"Configured organization {org_id} is not accessible")

        live_channels = {c["id"]: c for c in snapshot.get("channels", [])}
        missing = [meta["id"] for meta in self.channels.values() if meta["id"] not in live_channels]
        if missing:
            raise BufferAPIError(f"Configured Buffer channels are missing/disconnected: {missing}")
        if snapshot.get("has_next_page"):
            raise BufferAPIError("Active Buffer queue exceeded one runtime snapshot page; refusing unsafe capacity inference")

        posts = list(snapshot.get("posts") or [])
        executions = self.expand()
        ideas: list[dict[str, Any]] = []
        if self.settings.get("content_source") == "socialmarket_outbox":
            self.actions.append({"type": "content_source", "source": "socialmarket_outbox", "executions": len(executions)})
        else:
            ideas = self.client.ideas(org_id)
            self.ensure_ideas(executions, ideas)

        self.reconcile_and_fill(executions, posts)
        per_channel_limit = int(self.settings.get("queue_limit_per_channel", 10))
        initial_active_by_service = {
            service: sum(1 for p in posts if p.get("status") in core.ACTIVE_QUEUE_STATUSES and p.get("channelId") == meta["id"])
            for service, meta in self.channels.items()
        }
        accepted_action = "scheduled" if self.mode == "live" else "would_schedule"
        scheduled_by_service = {
            service: sum(1 for action in self.actions if action.get("type") == accepted_action and action.get("service") == service)
            for service in self.channels
        }
        post_write_active_by_service = {
            service: min(per_channel_limit, initial_active_by_service.get(service, 0) + scheduled_by_service.get(service, 0))
            for service in self.channels
        }
        channel_queue_slo = {
            service: {
                "active": post_write_active_by_service.get(service, 0),
                "limit": per_channel_limit,
                "missing": max(0, per_channel_limit - post_write_active_by_service.get(service, 0)),
                "fill_rate_pct": round(100.0 * post_write_active_by_service.get(service, 0) / max(1, per_channel_limit), 2),
                "met": post_write_active_by_service.get(service, 0) >= per_channel_limit,
            }
            for service in self.channels
        }
        for service, truth in channel_queue_slo.items():
            if not truth["met"]:
                self.actions.append({
                    "type": "queue_underfilled",
                    "severity": "CRITICAL",
                    "service": service,
                    "channelId": self.channels[service]["id"],
                    "active": truth["active"],
                    "limit": truth["limit"],
                    "missing_slots": truth["missing"],
                    "reason": "approved_supply_or_execution_shortage",
                })

        total_active = sum(post_write_active_by_service.values())
        total_limit = per_channel_limit * len(self.channels)
        total_missing = max(0, total_limit - total_active)
        queue_slo = {
            "active": total_active,
            "limit": total_limit,
            "missing": total_missing,
            "fill_rate_pct": round(100.0 * total_active / max(1, total_limit), 2),
            "met": all(row["met"] for row in channel_queue_slo.values()),
            "severity": "OK" if all(row["met"] for row in channel_queue_slo.values()) else "CRITICAL",
        }

        service_by_channel = {meta["id"]: service for service, meta in self.channels.items()}
        next_scheduled = [
            {
                "id": post.get("id"),
                "service": service_by_channel.get(post.get("channelId"), "unknown"),
                "channelId": post.get("channelId"),
                "dueAt": post.get("dueAt"),
                "source": "buffer_snapshot",
            }
            for post in posts if post.get("status") in core.ACTIVE_QUEUE_STATUSES
        ]
        next_scheduled.extend(
            {
                "id": action.get("postId"),
                "service": action.get("service"),
                "channelId": (self.channels.get(str(action.get("service"))) or {}).get("id"),
                "dueAt": action.get("dueAt"),
                "source": "buffer_create_ack" if self.mode == "live" else "dry_run",
            }
            for action in self.actions if action.get("type") == accepted_action
        )
        next_scheduled.sort(key=lambda row: str(row.get("dueAt") or ""))

        return {
            "mode": self.mode,
            "organization": org_id,
            "timezone": self.settings["timezone"],
            "content_source": self.settings.get("content_source", "legacy_backlog"),
            "posts_seen": len(posts),
            "ideas_seen": len(ideas),
            "initial_active_queue": sum(initial_active_by_service.values()),
            "initial_active_by_service": initial_active_by_service,
            "scheduled_by_service": scheduled_by_service,
            "active_queue": total_active,
            "active_by_service": post_write_active_by_service,
            "queue_limit_per_channel": per_channel_limit,
            "queue_slo": queue_slo,
            "channel_queue_slo": channel_queue_slo,
            "next_scheduled": next_scheduled,
            "full_truth_source": "single_runtime_snapshot_plus_buffer_create_ack",
            "actions": self.actions,
        }
