from __future__ import annotations

from typing import Any

from .openpost_client import (
    OpenPostAPIError,
    OpenPostClient as BaseOpenPostClient,
    _iso_utc,
    _render_content,
)

SERVICES = ("facebook", "instagram", "tiktok", "linkedin")


def _native_profile(platform: str, fmt: str | None) -> str:
    value = (fmt or "post").strip().lower()
    if platform == "instagram":
        if value in {"story", "ig_story", "instagram_story"}:
            return "story"
        if value in {"reel", "short_video", "video"}:
            return "short_video"
        return "post"
    if platform == "tiktok":
        if "story" in value:
            raise OpenPostAPIError("TikTok Story is not supported by the current OpenPost publishing path")
        if value in {"photo", "image", "post", "feed"}:
            return "post"
        return "short_video"
    if platform in {"linkedin", "facebook"}:
        if "story" in value and platform == "facebook":
            return "story"
        if value in {"video", "short_video"}:
            return "short_video"
        return "post"
    raise OpenPostAPIError(f"Unsupported OpenPost platform: {platform}")


class OpenPostClient(BaseOpenPostClient):
    @staticmethod
    def account_ids_from_env() -> dict[str, str]:
        import os

        return {
            service: value
            for service in SERVICES
            if (value := os.getenv(f"OPENPOST_ACCOUNT_{service.upper()}", "").strip())
        }

    def create_publication(self, job: dict[str, Any], account_id: str) -> dict[str, Any]:
        job_id = str(job.get("id") or "").strip()
        platform = str(job.get("platform") or "").strip().lower()
        scheduled_for = str(job.get("scheduled_for") or "").strip()
        if not job_id or platform not in SERVICES or not scheduled_for:
            raise OpenPostAPIError("OpenPost job requires id, supported platform and scheduled_for")

        content = _render_content(job)
        if not content:
            raise OpenPostAPIError("OpenPost job has no publishable content")

        profile = _native_profile(platform, str(job.get("format") or ""))
        media_url = str(job.get("media_url") or "").strip()
        media: list[dict[str, Any]] = []
        if media_url:
            media = [{"media_id": self.upload_from_url(media_url), "role": "attachment"}]
        elif platform in {"instagram", "tiktok"}:
            raise OpenPostAPIError(f"{platform} job requires media_url")

        title = str(job.get("title") or "Approved content").strip()
        payload = {
            "workspace_id": self.workspace_id,
            "title": f"SOCIALMARKET {job_id} | {title}"[:240],
            "creation_preset": profile,
            "content_profile": profile,
            "source_text": content,
            "source_url": str(job.get("tracking_url") or "").strip(),
            "scheduled_at": _iso_utc(scheduled_for),
            "random_delay_minutes": 0,
            "metadata": {
                "source": "socialscheduler",
                "publisher": "openpost",
                "socialmarket_job_id": job_id,
                "platform": platform,
                "format": str(job.get("format") or "post").strip().lower(),
                "tracking_url": str(job.get("tracking_url") or "").strip(),
            },
            "social_account_ids": [account_id],
            "media": media,
        }
        result = self._request_json("POST", "/publications", payload, write=True)
        if not isinstance(result, dict) or not result.get("id") or not result.get("revision"):
            raise OpenPostAPIError("OpenPost create-publication returned no id/revision", ambiguous=True)
        return dict(result)
