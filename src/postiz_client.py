from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


class PostizAPIError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


_PLATFORM_IDENTIFIERS = {
    "facebook": {"facebook"},
    "instagram": {"instagram", "instagram-standalone"},
    "tiktok": {"tiktok"},
}


def _iso_utc(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _post_type(fmt: str | None) -> str:
    value = (fmt or "").strip().lower()
    if "reel" in value or "video" in value:
        return "reel"
    if "story" in value:
        return "story"
    return "post"


def _render_content(job: dict[str, Any]) -> str:
    caption = str(job.get("caption") or "").strip()
    hashtags = [str(x).strip() for x in (job.get("hashtags") or []) if str(x).strip()]
    tracking = str(job.get("tracking_url") or "").strip()
    parts = [caption]
    if hashtags:
        parts.append(" ".join(tag for tag in hashtags if tag not in caption))
    if tracking and tracking not in caption:
        parts.append(tracking)
    return "\n\n".join(part for part in parts if part).strip()


@dataclass
class PostizClient:
    api_url: str
    api_key: str
    timeout_seconds: int = 30

    @classmethod
    def from_env(cls) -> "PostizClient":
        api_url = os.getenv("POSTIZ_API_URL", "https://api.postiz.com/public/v1").strip().rstrip("/")
        api_key = os.getenv("POSTIZ_API_KEY", "").strip()
        if not api_key:
            raise PostizAPIError("POSTIZ_API_KEY is required")
        return cls(api_url=api_url, api_key=api_key)

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Authorization": self.api_key, "Accept": "application/json", "User-Agent": "socialscheduler-postiz/1.0"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(f"{self.api_url}{path}", data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:2000]
            except Exception:
                pass
            raise PostizAPIError(f"Postiz HTTP {exc.code}: {detail or exc.reason}", status_code=exc.code) from exc
        except Exception as exc:
            raise PostizAPIError(f"Postiz request failed: {exc}") from exc

    def is_connected(self) -> bool:
        result = self._request("GET", "/is-connected") or {}
        return bool(result.get("connected"))

    def integrations(self) -> list[dict[str, Any]]:
        result = self._request("GET", "/integrations")
        return list(result or [])

    def resolve_integrations(self) -> dict[str, str]:
        integrations = [row for row in self.integrations() if not row.get("disabled")]
        resolved: dict[str, str] = {}
        for platform, identifiers in _PLATFORM_IDENTIFIERS.items():
            explicit = os.getenv(f"POSTIZ_INTEGRATION_{platform.upper()}", "").strip()
            if explicit:
                resolved[platform] = explicit
                continue
            matches = [row for row in integrations if str(row.get("identifier") or "") in identifiers]
            if len(matches) == 1:
                resolved[platform] = str(matches[0].get("id") or "")
            elif len(matches) > 1:
                raise PostizAPIError(
                    f"Multiple Postiz {platform} integrations are connected; set POSTIZ_INTEGRATION_{platform.upper()} explicitly"
                )
        return {platform: integration_id for platform, integration_id in resolved.items() if integration_id}

    def upload_from_url(self, media_url: str) -> dict[str, Any]:
        result = self._request("POST", "/upload-from-url", {"url": media_url})
        if not isinstance(result, dict) or not result.get("id") or not result.get("path"):
            raise PostizAPIError("Postiz upload-from-url returned an invalid media object")
        return result

    def schedule_job(self, job: dict[str, Any], integration_id: str) -> dict[str, Any]:
        platform = str(job.get("platform") or "").strip().lower()
        if platform not in _PLATFORM_IDENTIFIERS:
            raise PostizAPIError(f"Unsupported Postiz platform: {platform}")
        scheduled_for = str(job.get("scheduled_for") or "").strip()
        if not scheduled_for:
            raise PostizAPIError("scheduled_for is required")

        media_url = str(job.get("media_url") or "").strip()
        images: list[dict[str, Any]] = []
        if media_url:
            media = self.upload_from_url(media_url)
            images = [{"id": media["id"], "path": media["path"]}]
        elif platform in {"instagram", "tiktok"}:
            raise PostizAPIError(f"{platform} job requires media_url")

        settings: dict[str, Any]
        if platform == "facebook":
            settings = {"__type": "facebook"}
            tracking = str(job.get("tracking_url") or "").strip()
            if tracking:
                settings["url"] = tracking
        elif platform == "instagram":
            settings = {
                "__type": "instagram",
                "post_type": _post_type(str(job.get("format") or "")),
                "is_trial_reel": False,
                "collaborators": [],
            }
        else:
            settings = {
                "__type": "tiktok",
                "title": str(job.get("title") or "")[:90],
                "privacy_level": "PUBLIC_TO_EVERYONE",
                "duet": False,
                "stitch": False,
                "comment": True,
                "autoAddMusic": "no",
                "brand_content_toggle": False,
                "brand_organic_toggle": False,
                "video_made_with_ai": False,
                "content_posting_method": "DIRECT_POST",
            }

        payload = {
            "type": "schedule",
            "date": _iso_utc(scheduled_for),
            "shortLink": False,
            "tags": [],
            "posts": [{
                "integration": {"id": integration_id},
                "value": [{"content": _render_content(job), "image": images}],
                "settings": settings,
            }],
        }
        result = self._request("POST", "/posts", payload)
        rows = list(result or []) if isinstance(result, list) else []
        if not rows or not rows[0].get("postId"):
            raise PostizAPIError("Postiz create-post returned no postId")
        return dict(rows[0])
