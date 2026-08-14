from __future__ import annotations

from datetime import datetime
from typing import Any

from . import scheduler as core
from .buffer_client import BufferAPIError
from .scheduler import Execution, SocialScheduler as BaseSocialScheduler

# A Buffer error is not automatically safe to retry: the destination network may
# have accepted the publish even when Buffer reports an error. Treat exact error
# executions as consumed until a deliberate recovery path classifies the error.
core.CONSUMED_STATUSES = {"scheduled", "sending", "sent", "error"}


class SocialScheduler(BaseSocialScheduler):
    """Production Buffer executor with conservative error handling.

    In SocialMarket outbox mode this class does not invent campaigns or Buffer Ideas.
    It receives already-approved executions and owns only scheduling/publishing.
    """

    def _post_input(self, ex: Execution, due_at: datetime) -> dict[str, Any]:
        data = super()._post_input(ex, due_at)
        if self.settings.get("content_source") == "socialmarket_outbox":
            data["source"] = f"socialmarket:{ex.campaign_id}:{ex.service}"
        return data

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
        super().reconcile_and_fill(executions, posts)

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
        executions = self.expand()

        if self.settings.get("content_source") == "socialmarket_outbox":
            ideas: list[dict[str, Any]] = []
            self.actions.append({"type": "content_source", "source": "socialmarket_outbox", "executions": len(executions)})
        else:
            ideas = self.client.ideas(org_id)
            self.ensure_ideas(executions, ideas)

        self.reconcile_and_fill(executions, posts)

        return {
            "mode": self.mode,
            "organization": org_id,
            "timezone": self.settings["timezone"],
            "content_source": self.settings.get("content_source", "legacy_backlog"),
            "posts_seen": len(posts),
            "ideas_seen": len(ideas),
            "active_queue": sum(1 for p in posts if p.get("status") in core.ACTIVE_QUEUE_STATUSES),
            "queue_limit": self.settings["queue_limit"],
            "buffer_posts": [
                {"id": p.get("id"), "status": p.get("status"), "dueAt": p.get("dueAt"), "sentAt": p.get("sentAt")}
                for p in posts if p.get("id")
            ],
            "actions": self.actions,
        }
