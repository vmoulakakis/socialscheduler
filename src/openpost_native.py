from __future__ import annotations

import hashlib
import io
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

    def _upload_bytes(self, content: bytes, filename: str, mime_type: str) -> str:
        digest = hashlib.sha256(content).hexdigest()
        session = self._request_json(
            "POST",
            "/media/upload-session",
            {
                "workspace_id": self.workspace_id,
                "filename": filename,
                "mime_type": mime_type,
                "size": len(content),
                "source": "upload",
                "retention_class": "temporary",
                "client_sha256": digest,
            },
            write=True,
        )
        if not isinstance(session, dict) or not session.get("media_id"):
            raise OpenPostAPIError("OpenPost create-media-upload-session returned an invalid response")
        media_id = str(session["media_id"])
        if not bool(session.get("deduped")):
            upload = session.get("upload")
            if not isinstance(upload, dict):
                raise OpenPostAPIError("OpenPost media upload session returned no upload target")
            self._upload_binary(upload, content, mime_type)
            complete_url = str(session.get("complete_url") or f"/media/upload-session/{media_id}/complete")
            completed = self._request_json(
                "POST",
                complete_url,
                {"workspace_id": self.workspace_id},
                write=True,
            )
            if isinstance(completed, dict) and completed.get("id"):
                media_id = str(completed["id"])
        self._wait_media_ready(media_id)
        return media_id

    def upload_tiktok_photo_from_url(self, media_url: str) -> str:
        content, filename, mime_type, _ = self._download_media(media_url)
        normalized = mime_type.strip().lower()
        if normalized in {"image/jpeg", "image/webp"}:
            return self._upload_bytes(content, filename, normalized)
        if not normalized.startswith("image/"):
            raise OpenPostAPIError(
                f"TikTok photo post requires image media; approved asset was {mime_type or 'unknown'}"
            )
        try:
            from PIL import Image
        except ImportError as exc:  # pragma: no cover - deployment guard
            raise OpenPostAPIError("Pillow is required for TikTok image normalization") from exc
        try:
            with Image.open(io.BytesIO(content)) as image:
                output = io.BytesIO()
                image.save(output, format="WEBP", lossless=True, method=6)
                converted = output.getvalue()
        except Exception as exc:
            raise OpenPostAPIError(f"Unable to normalize TikTok photo creative to WebP: {exc}") from exc
        if not converted:
            raise OpenPostAPIError("TikTok WebP normalization produced an empty image")
        stem = filename.rsplit(".", 1)[0] if "." in filename else filename
        return self._upload_bytes(converted, f"{stem}.webp", "image/webp")

    def create_publication(self, job: dict[str, Any], account_id: str) -> dict[str, Any]:
        job_id = str(job.get("id") or "").strip()
        platform = str(job.get("platform") or "").strip().lower()
        scheduled_for = str(job.get("scheduled_for") or "").strip()
        if not job_id or platform not in SERVICES or not scheduled_for:
            raise OpenPostAPIError("OpenPost job requires id, supported platform and scheduled_for")

        content = _render_content(job)
        if not content:
            raise OpenPostAPIError("OpenPost job has no publishable content")

        fmt = str(job.get("format") or "post").strip().lower()
        profile = _native_profile(platform, fmt)
        media_url = str(job.get("media_url") or "").strip()
        media: list[dict[str, Any]] = []
        if media_url:
            if platform == "tiktok" and profile == "post":
                media_id = self.upload_tiktok_photo_from_url(media_url)
            else:
                media_id = self.upload_from_url(media_url)
            media = [{"media_id": media_id, "role": "attachment"}]
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
                "format": fmt,
                "tracking_url": str(job.get("tracking_url") or "").strip(),
            },
            "social_account_ids": [account_id],
            "media": media,
        }
        result = self._request_json("POST", "/publications", payload, write=True)
        if not isinstance(result, dict) or not result.get("id") or not result.get("revision"):
            raise OpenPostAPIError("OpenPost create-publication returned no id/revision", ambiguous=True)
        return dict(result)
