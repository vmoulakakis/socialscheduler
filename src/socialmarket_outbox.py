from __future__ import annotations

import json
import os
import time
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
    request_timeout_seconds: int = 30
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
            headers={"Authorization": f"Bearer {request_token}", "User-Agent": "socialscheduler/3.0"},
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
        for attempt in range(3):
            req = urllib.request.Request(
                self.endpoint,
                data=body,
                headers={
                    "Authorization": f"Bearer {self._github_oidc_token()}",
                    "Content-Type": "application/json",
                    "User-Agent": "socialscheduler/3.0",
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
                transient = exc.code in {502, 503, 504} or "request timed out" in detail.lower()
                if transient and attempt < 2:
                    time.sleep(attempt + 1)
                    continue
                raise SocialMarketOutboxError(f"SocialMarket outbox HTTP {exc.code}: {detail or exc.reason}") from exc
            except Exception as exc:
                if attempt < 2:
                    time.sleep(attempt + 1)
                    continue
                raise SocialMarketOutboxError(f"SocialMarket outbox request failed: {exc}") from exc
            if not result.get("ok"):
                raise SocialMarketOutboxError(str(result.get("error") or "SocialMarket outbox returned an error"))
            return result
        raise SocialMarketOutboxError("SocialMarket outbox request failed after retries")

    def health(self) -> dict[str, Any]:
        return self._post({"action": "health"})

    def refill(self, hours: int = 72) -> dict[str, Any]:
        return dict(self._post({"action": "refill", "hours": hours}).get("refill") or {})

    def peek(self, limit: int = 10) -> list[dict[str, Any]]:
        return list(self._post({"action": "peek", "limit": limit}).get("jobs") or [])

    def claim(self, limit: int = 10, lease_minutes: int = 30) -> list[dict[str, Any]]:
        return list(self._post({
            "action": "claim",
            "executor": "socialscheduler",
            "limit": limit,
            "lease_minutes": lease_minutes,
        }).get("jobs") or [])

    def claim_capacity(self, capacity: dict[str, int], lease_minutes: int = 30) -> list[dict[str, Any]]:
        safe = {name: max(0, min(10, int(capacity.get(name, 0)))) for name in ("facebook", "instagram", "tiktok")}
        return list(self._post({
            "action": "claim_capacity",
            "executor": "socialscheduler",
            "capacity": safe,
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

    def metrics_batch(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        return dict(self._post({"action": "metrics_batch", "rows": rows}).get("result") or {})

    def optimize_week(self, week_start: str) -> dict[str, Any]:
        return dict(self._post({"action": "optimize_week", "week_start": week_start}).get("result") or {})

    def sync_scheduler_actions(self, actions: list[dict[str, Any]]) -> dict[str, int]:
        """Archive successful Buffer schedules immediately; keep only failures in outbox."""
        counts = {"scheduled_archived": 0, "failed": 0}
        for action in actions:
            job_id = str(action.get("campaign") or "").strip()
            if not job_id:
                continue
            action_type = action.get("type")
            platform_meta = {"platform": action.get("service"), "scheduler_version": "v3"}
            if action_type == "scheduled":
                self.ack(
                    job_id,
                    "scheduled",
                    external_post_id=action.get("postId"),
                    scheduled_at=action.get("dueAt"),
                    metadata=platform_meta | {"archive_after_schedule": True},
                )
                counts["scheduled_archived"] += 1
            elif action_type in {"already_error", "skip_late"}:
                reason = action.get("reason") or ("scheduled_time_elapsed" if action_type == "skip_late" else "buffer_status_error")
                self.ack(job_id, "failed", external_post_id=action.get("postId"), error=reason, metadata=platform_meta)
                counts["failed"] += 1
            elif action_type == "blocked" and action.get("reason") in {"media_unavailable", "fresh_verification_required"}:
                self.ack(job_id, "failed", error=action.get("reason"), metadata=platform_meta)
                counts["failed"] += 1
        return counts
