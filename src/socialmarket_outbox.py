from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable


class SocialMarketOutboxError(RuntimeError):
    pass


def _merge_caption_and_hashtags(caption: str, hashtags: list[str] | None) -> str:
    text = (caption or "").strip()
    extra = [tag.strip() for tag in (hashtags or []) if tag and tag.strip() and tag.strip() not in text]
    return f"{text}\n\n{' '.join(extra)}".strip() if extra else text


def jobs_to_backlog(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    backlog: list[dict[str, Any]] = []
    for job in jobs:
        platform = str(job.get("platform") or "").strip()
        target_at = job.get("scheduled_for")
        caption = str(job.get("caption") or "").strip()
        job_id = str(job.get("id") or "").strip()
        if platform not in {"facebook", "instagram", "tiktok"} or not job_id or not target_at or not caption:
            continue
        backlog.append({
            "id": job_id,
            "brand": job.get("brand_name") or job.get("brand_slug") or "SocialMarket",
            "topic": job.get("title") or "Approved content",
            "idea_title": f"SOCIALMARKET | {job.get('title') or job_id}",
            "target_at": target_at,
            "services": [platform],
            "media_url": job.get("media_url"),
            "format": {platform: job.get("format") or "post"},
            "platform_text": {platform: _merge_caption_and_hashtags(caption, job.get("hashtags"))},
            "tracking_url": job.get("tracking_url"),
        })
    return backlog


@dataclass
class SocialMarketOutboxClient:
    endpoint: str
    audience: str = "socialmarket-v2-publishing"
    request_timeout_seconds: int = 20
    token_provider: Callable[[], str] | None = None

    @classmethod
    def from_env(cls) -> "SocialMarketOutboxClient":
        endpoint = os.getenv("SOCIALMARKET_OUTBOX_URL", "").strip()
        if not endpoint:
            raise SocialMarketOutboxError("SOCIALMARKET_OUTBOX_URL is required in SocialMarket outbox mode")
        audience = os.getenv("SOCIALMARKET_OIDC_AUDIENCE", "socialmarket-v2-publishing").strip() or "socialmarket-v2-publishing"
        return cls(endpoint=endpoint.rstrip("/"), audience=audience)

    def _github_oidc_token(self) -> str:
        if self.token_provider:
            return self.token_provider()
        request_url = os.getenv("ACTIONS_ID_TOKEN_REQUEST_URL", "").strip()
        request_token = os.getenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "").strip()
        if not request_url or not request_token:
            raise SocialMarketOutboxError("GitHub Actions OIDC environment is unavailable; id-token: write permission is required")
        parsed = urllib.parse.urlsplit(request_url)
        query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        query = [(k, v) for k, v in query if k != "audience"] + [("audience", self.audience)]
        oidc_url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), parsed.fragment))
        req = urllib.request.Request(
            oidc_url,
            headers={"Authorization": f"Bearer {request_token}", "User-Agent": "socialscheduler/2.2"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.request_timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise SocialMarketOutboxError(f"Unable to obtain GitHub OIDC token: {exc}") from exc
        token = str(payload.get("value") or "").strip()
        if not token:
            raise SocialMarketOutboxError("GitHub OIDC response did not contain a token")
        return token

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {self._github_oidc_token()}",
                "Content-Type": "application/json",
                "User-Agent": "socialscheduler/2.2",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.request_timeout_seconds) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:2000]
            except Exception:
                pass
            raise SocialMarketOutboxError(f"SocialMarket outbox HTTP {exc.code}: {detail or exc.reason}") from exc
        except Exception as exc:
            raise SocialMarketOutboxError(f"SocialMarket outbox request failed: {exc}") from exc
        if not result.get("ok"):
            raise SocialMarketOutboxError(str(result.get("error") or "SocialMarket outbox returned an error"))
        return result

    def health(self) -> dict[str, Any]:
        return self._post({"action": "health"})

    def peek(self, limit: int = 10) -> list[dict[str, Any]]:
        return list(self._post({"action": "peek", "limit": limit}).get("jobs") or [])

    def claim(self, limit: int = 10, lease_minutes: int = 30) -> list[dict[str, Any]]:
        return list(self._post({
            "action": "claim",
            "executor": "socialscheduler",
            "limit": limit,
            "lease_minutes": lease_minutes,
        }).get("jobs") or [])

    def ack(self, job_id: str, status: str, *, external_post_id: str | None = None,
            external_permalink: str | None = None, scheduled_at: str | None = None,
            published_at: str | None = None, error: str | None = None,
            metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._post({
            "action": "ack", "job_id": job_id, "status": status,
            "external_post_id": external_post_id, "external_permalink": external_permalink,
            "scheduled_at": scheduled_at, "published_at": published_at,
            "error": error, "metadata": metadata or {},
        })

    def reconcile_jobs(self, limit: int = 200) -> list[dict[str, Any]]:
        return list(self._post({"action": "reconcile", "limit": limit}).get("jobs") or [])

    def sync_scheduler_actions(self, actions: list[dict[str, Any]]) -> dict[str, int]:
        counts = {"scheduled": 0, "published": 0, "failed": 0}
        for action in actions:
            job_id = str(action.get("campaign") or "").strip()
            if not job_id:
                continue
            action_type = action.get("type")
            platform_meta = {"platform": action.get("service")}
            if action_type in {"scheduled", "already_scheduled"}:
                self.ack(job_id, "scheduled", external_post_id=action.get("postId"),
                         scheduled_at=action.get("dueAt"),
                         metadata=platform_meta | {"reconciled_existing": action_type == "already_scheduled"})
                counts["scheduled"] += 1
            elif action_type == "already_published":
                self.ack(job_id, "published", external_post_id=action.get("postId"),
                         published_at=action.get("sentAt"),
                         metadata=platform_meta | {"reconciled_existing": True})
                counts["published"] += 1
            elif action_type in {"already_error", "skip_late"}:
                reason = action.get("reason") or ("scheduled_time_elapsed" if action_type == "skip_late" else "buffer_status_error")
                self.ack(job_id, "failed", external_post_id=action.get("postId"), error=reason, metadata=platform_meta)
                counts["failed"] += 1
            elif action_type == "blocked" and action.get("reason") in {"media_unavailable", "fresh_verification_required"}:
                self.ack(job_id, "failed", error=action.get("reason"), metadata=platform_meta)
                counts["failed"] += 1
        return counts

    def sync_buffer_statuses(self, tracked_jobs: list[dict[str, Any]], buffer_posts: list[dict[str, Any]]) -> dict[str, int]:
        by_id = {str(post.get("id")): post for post in buffer_posts if post.get("id")}
        counts = {"published": 0, "failed": 0, "scheduled": 0}
        for job in tracked_jobs:
            external_id = str(job.get("external_post_id") or "").strip()
            if not external_id or external_id not in by_id:
                continue
            post = by_id[external_id]
            status = post.get("status")
            job_id = str(job.get("id"))
            if status == "sent":
                self.ack(job_id, "published", external_post_id=external_id, published_at=post.get("sentAt"))
                counts["published"] += 1
            elif status == "error":
                self.ack(job_id, "failed", external_post_id=external_id, error="buffer_status_error")
                counts["failed"] += 1
            elif status in {"scheduled", "sending"} and job.get("status") != "scheduled":
                self.ack(job_id, "scheduled", external_post_id=external_id, scheduled_at=post.get("dueAt"))
                counts["scheduled"] += 1
        return counts
