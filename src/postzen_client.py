from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class PostZenAPIError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def compose_text(job: dict[str, Any]) -> str:
    text = str(job.get("caption") or "").strip()
    hashtags = [str(x).strip() for x in (job.get("hashtags") or []) if str(x).strip()]
    extras = [x for x in hashtags if x not in text]
    if extras:
        text = f"{text}\n\n{' '.join(extras)}".strip()
    tracking = str(job.get("tracking_url") or "").strip()
    if tracking and tracking not in text:
        text = f"{text}\n\n{tracking}".strip()
    return text


def _canonical_platform(value: str) -> str:
    platform = value.strip().lower()
    return "x" if platform == "twitter" else platform


@dataclass
class PostZenClient:
    api_url: str
    api_key: str
    timeout_seconds: int = 30

    @classmethod
    def from_env(cls) -> "PostZenClient":
        api_url = os.getenv("POSTZEN_API_URL", "https://api.postzen.dev").strip().rstrip("/")
        api_key = os.getenv("POSTZEN_API_KEY", "").strip()
        if not api_key:
            raise PostZenAPIError("POSTZEN_API_KEY is required")
        return cls(api_url=api_url, api_key=api_key, timeout_seconds=int(os.getenv("POSTZEN_TIMEOUT_SECONDS", "30")))

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        extra_headers: dict[str, str] | None = None,
    ) -> Any:
        url = f"{self.api_url}/{path.lstrip('/')}"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "User-Agent": "socialscheduler/postzen-2.0",
        }
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if extra_headers:
            headers.update({str(k): str(v) for k, v in extra_headers.items() if v is not None})
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:3000]
            except Exception:
                pass
            raise PostZenAPIError(
                f"PostZen HTTP {exc.code}: {detail or exc.reason}",
                status_code=exc.code,
            ) from exc
        except Exception as exc:
            raise PostZenAPIError(f"PostZen request failed: {exc}") from exc

    def list_accounts(self) -> list[dict[str, Any]]:
        result = self._request("GET", "/v1/accounts")
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            rows = result.get("accounts") or result.get("data") or []
            return list(rows) if isinstance(rows, list) else []
        return []

    def connected_platforms(self) -> set[str]:
        platforms: set[str] = set()
        for account in self.list_accounts():
            if str(account.get("status") or "connected").lower() != "connected":
                continue
            if account.get("isActive") is False:
                continue
            platform = _canonical_platform(str(account.get("platform") or ""))
            if platform:
                platforms.add(platform)
        return platforms

    def resolve_account(self, platform: str) -> dict[str, Any]:
        """Resolve exactly one executable PostZen account for a platform.

        A configured POSTZEN_ACCOUNT_<PLATFORM> id wins. Otherwise exactly one
        connected active account must exist. This intentionally refuses an
        ambiguous account selection instead of publishing to the wrong account.
        """
        canonical = _canonical_platform(platform)
        configured = os.getenv(f"POSTZEN_ACCOUNT_{canonical.upper()}", "").strip()
        candidates = [
            account
            for account in self.list_accounts()
            if str(account.get("status") or "connected").lower() == "connected"
            and account.get("isActive") is not False
            and _canonical_platform(str(account.get("platform") or "")) == canonical
        ]
        if configured:
            matches = [
                account
                for account in candidates
                if configured
                in {
                    str(account.get("_id") or ""),
                    str(account.get("id") or ""),
                    str(account.get("providerAccountId") or ""),
                }
            ]
            if len(matches) == 1:
                return matches[0]
            raise PostZenAPIError(
                f"Configured PostZen {canonical} account is not connected/active",
                status_code=422,
            )
        if len(candidates) == 1:
            return candidates[0]
        if not candidates:
            raise PostZenAPIError(
                f"No connected active PostZen account for {canonical}",
                status_code=422,
            )
        raise PostZenAPIError(
            f"Multiple connected PostZen accounts for {canonical}; configure POSTZEN_ACCOUNT_{canonical.upper()}",
            status_code=422,
        )

    @staticmethod
    def _account_id(account: dict[str, Any]) -> str:
        # Current PostZen CreatePostTarget accepts either PostZen account id or
        # provider account id. Prefer the stable PostZen account id.
        return str(
            account.get("_id")
            or account.get("id")
            or account.get("providerAccountId")
            or ""
        ).strip()

    def schedule_job(self, job: dict[str, Any]) -> dict[str, Any]:
        platform = _canonical_platform(str(job.get("platform") or ""))
        scheduled_for = str(job.get("scheduled_for") or "").strip()
        if platform == "tiktok":
            raise PostZenAPIError("TikTok is not enabled for PostZen routing", status_code=422)
        if not platform or not scheduled_for:
            raise PostZenAPIError("Job is missing platform or scheduled_for", status_code=422)
        text = compose_text(job)
        if not text:
            raise PostZenAPIError("Job caption is empty", status_code=422)

        account = self.resolve_account(platform)
        account_id = self._account_id(account)
        if not account_id:
            raise PostZenAPIError(
                f"Connected PostZen {platform} account has no usable account id",
                status_code=422,
            )

        # PostZen Public API v1 current CreatePostRequest contract:
        # content + mediaItems + platforms[{platform,accountId}] + scheduledFor.
        # Exactly one creation mode is used; this executor always schedules.
        payload: dict[str, Any] = {
            "title": str(job.get("title") or "SocialScheduler").strip()[:200] or "SocialScheduler",
            "content": text,
            "platforms": [{"platform": platform, "accountId": account_id}],
            "scheduledFor": scheduled_for,
            "timezone": "UTC",
        }
        media_url = str(job.get("media_url") or "").strip()
        if media_url:
            payload["mediaItems"] = [
                {
                    "url": media_url,
                    "title": str(job.get("title") or "").strip()[:200] or None,
                }
            ]

        # The official SDK exposes x_request_id on create_post. Using the
        # canonical outbox job id makes retries safe against duplicate creation.
        request_id = str(job.get("id") or "").strip()
        result = self._request(
            "POST",
            "/v1/posts",
            payload,
            extra_headers={"X-Request-Id": request_id} if request_id else None,
        )
        return result if isinstance(result, dict) else {"data": result}

    @staticmethod
    def extract_post_id(result: dict[str, Any]) -> str:
        post = result.get("post") if isinstance(result.get("post"), dict) else {}
        existing = result.get("existingPost") if isinstance(result.get("existingPost"), dict) else {}
        data = result.get("data") if isinstance(result.get("data"), dict) else {}
        candidates = [
            result.get("id"),
            result.get("_id"),
            post.get("id"),
            post.get("_id"),
            existing.get("id"),
            existing.get("_id"),
            data.get("id"),
            data.get("_id"),
        ]
        for value in candidates:
            if value:
                return str(value)
        posts = result.get("posts")
        if isinstance(posts, list) and posts and isinstance(posts[0], dict):
            value = posts[0].get("id") or posts[0].get("_id")
            if value:
                return str(value)
        return ""

    @staticmethod
    def extract_permalink(result: dict[str, Any]) -> str:
        for root in (result, result.get("post"), result.get("existingPost"), result.get("data")):
            if not isinstance(root, dict):
                continue
            for key in ("permalink", "url", "postUrl", "platformPostUrl"):
                if root.get(key):
                    return str(root[key])
            platforms = root.get("platforms")
            if isinstance(platforms, list):
                for target in platforms:
                    if isinstance(target, dict) and target.get("platformPostUrl"):
                        return str(target["platformPostUrl"])
        return ""
