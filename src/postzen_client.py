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

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        url = f"{self.api_url}/{path.lstrip('/')}"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "User-Agent": "socialscheduler/postzen-1.0",
        }
        if payload is not None:
            headers["Content-Type"] = "application/json"
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
            platform = str(account.get("platform") or "").strip().lower()
            if platform:
                platforms.add(platform)
        return platforms

    def schedule_job(self, job: dict[str, Any]) -> dict[str, Any]:
        platform = str(job.get("platform") or "").strip().lower()
        scheduled_for = str(job.get("scheduled_for") or "").strip()
        if platform == "tiktok":
            raise PostZenAPIError("TikTok is not enabled for PostZen routing", status_code=422)
        if not platform or not scheduled_for:
            raise PostZenAPIError("Job is missing platform or scheduled_for", status_code=422)
        text = compose_text(job)
        if not text:
            raise PostZenAPIError("Job caption is empty", status_code=422)
        payload: dict[str, Any] = {
            "text": text,
            "channels": [platform],
            "scheduledFor": scheduled_for,
        }
        media_url = str(job.get("media_url") or "").strip()
        if media_url:
            payload["mediaUrls"] = [media_url]
        result = self._request("POST", "/v1/posts", payload)
        return result if isinstance(result, dict) else {"data": result}

    @staticmethod
    def extract_post_id(result: dict[str, Any]) -> str:
        candidates = [
            result.get("id"),
            (result.get("post") or {}).get("id") if isinstance(result.get("post"), dict) else None,
            (result.get("data") or {}).get("id") if isinstance(result.get("data"), dict) else None,
        ]
        for value in candidates:
            if value:
                return str(value)
        posts = result.get("posts")
        if isinstance(posts, list) and posts and isinstance(posts[0], dict) and posts[0].get("id"):
            return str(posts[0]["id"])
        return ""

    @staticmethod
    def extract_permalink(result: dict[str, Any]) -> str:
        for key in ("permalink", "url", "postUrl"):
            if result.get(key):
                return str(result[key])
        data = result.get("data")
        if isinstance(data, dict):
            for key in ("permalink", "url", "postUrl"):
                if data.get(key):
                    return str(data[key])
        return ""
