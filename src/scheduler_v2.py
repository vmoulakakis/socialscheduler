from __future__ import annotations

from typing import Any

from . import scheduler as core
from .scheduler import Execution, SocialScheduler as BaseSocialScheduler

# A Buffer error is not automatically safe to retry: the destination network may
# have accepted the publish even when Buffer reports an error. Treat exact error
# executions as consumed until a deliberate recovery path classifies the error.
core.CONSUMED_STATUSES = {"scheduled", "sending", "sent", "error"}


class SocialScheduler(BaseSocialScheduler):
    """Production scheduler with conservative error handling."""

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
