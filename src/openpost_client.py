from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


class OpenPostAPIError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        ambiguous: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.ambiguous = ambiguous


SERVICES = ("facebook", "instagram", "tiktok")


def _iso_utc(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _content_profile(platform: str, fmt: str | None) -> str:
    value = (fmt or "").strip().lower()
    if "story" in value:
        return "story"
    if "reel" in value or "video" in value or "short" in value:
        return "short_video"
    if platform == "tiktok":
        return "short_video"
    return "post"


def _render_content(job: dict[str, Any]) -> str:
    caption = str(job.get("caption") or "").strip()
    hashtags = [str(value).strip() for value in (job.get("hashtags") or []) if str(value).strip()]
    tracking_url = str(job.get("tracking_url") or "").strip()
    parts = [caption]
    if hashtags:
        extra = [tag for tag in hashtags if tag not in caption]
        if extra:
            parts.append(" ".join(extra))
    if tracking_url and tracking_url not in caption:
        parts.append(tracking_url)
    return "\n\n".join(part for part in parts if part).strip()


@dataclass
class OpenPostClient:
    api_url: str
    api_token: str
    workspace_id: str
    timeout_seconds: int = 30
    media_max_bytes: int = 100 * 1024 * 1024
    media_ready_timeout_seconds: int = 90

    @classmethod
    def from_env(cls) -> "OpenPostClient":
        api_url = os.getenv("OPENPOST_API_URL", "").strip().rstrip("/")
        api_token = os.getenv("OPENPOST_API_TOKEN", "").strip()
        workspace_id = os.getenv("OPENPOST_WORKSPACE_ID", "").strip()
        if not api_url:
            raise OpenPostAPIError("OPENPOST_API_URL is required and must include the OpenPost REST prefix, normally /api/v1")
        if not api_token:
            raise OpenPostAPIError("OPENPOST_API_TOKEN is required")
        if not workspace_id:
            raise OpenPostAPIError("OPENPOST_WORKSPACE_ID is required")
        return cls(
            api_url=api_url,
            api_token=api_token,
            workspace_id=workspace_id,
            timeout_seconds=max(5, int(os.getenv("OPENPOST_TIMEOUT_SECONDS", "30"))),
            media_max_bytes=max(1, int(os.getenv("OPENPOST_MEDIA_MAX_BYTES", str(100 * 1024 * 1024)))),
            media_ready_timeout_seconds=max(0, int(os.getenv("OPENPOST_MEDIA_READY_TIMEOUT_SECONDS", "90"))),
        )

    @staticmethod
    def account_ids_from_env() -> dict[str, str]:
        resolved: dict[str, str] = {}
        for service in SERVICES:
            value = os.getenv(f"OPENPOST_ACCOUNT_{service.upper()}", "").strip()
            if value:
                resolved[service] = value
        return resolved

    def _absolute_url(self, path_or_url: str) -> str:
        value = str(path_or_url or "").strip()
        if value.startswith("http://") or value.startswith("https://"):
            return value
        return f"{self.api_url}/{value.lstrip('/')}"

    def _request_json(
        self,
        method: str,
        path_or_url: str,
        payload: dict[str, Any] | None = None,
        *,
        query: dict[str, Any] | None = None,
        write: bool = False,
    ) -> Any:
        url = self._absolute_url(path_or_url)
        if query:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{urllib.parse.urlencode(query)}"
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json",
            "User-Agent": "socialscheduler-openpost/1.0",
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:3000]
            except Exception:
                pass
            raise OpenPostAPIError(
                f"OpenPost HTTP {exc.code}: {detail or exc.reason}",
                status_code=exc.code,
                ambiguous=False,
            ) from exc
        except Exception as exc:
            raise OpenPostAPIError(
                f"OpenPost request failed: {exc}",
                ambiguous=write,
            ) from exc

    def health(self) -> dict[str, Any]:
        rows = self.list_publications(limit=1)
        return {"ok": True, "workspace_id": self.workspace_id, "sample_count": len(rows)}

    def list_publications(self, *, search: str = "", status: str = "", limit: int = 50) -> list[dict[str, Any]]:
        query: dict[str, Any] = {
            "workspace_id": self.workspace_id,
            "limit": max(1, min(200, int(limit))),
        }
        if search:
            query["search"] = search
        if status:
            query["status"] = status
        result = self._request_json("GET", "/publications", query=query)
        if not isinstance(result, list):
            raise OpenPostAPIError("OpenPost list-publications returned an invalid response")
        return [dict(row) for row in result if isinstance(row, dict)]

    def get_publication(self, publication_id: str) -> dict[str, Any]:
        result = self._request_json("GET", f"/publications/{urllib.parse.quote(publication_id, safe='')}")
        if not isinstance(result, dict):
            raise OpenPostAPIError("OpenPost get-publication returned an invalid response")
        return dict(result)

    def find_job_publication(self, job_id: str, platform: str) -> dict[str, Any] | None:
        matches: list[dict[str, Any]] = []
        for row in self.list_publications(search=job_id, limit=50):
            metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
            if str(metadata.get("socialmarket_job_id") or "") != job_id:
                continue
            if str(metadata.get("platform") or "").lower() != platform:
                continue
            matches.append(row)
        if len(matches) > 1:
            raise OpenPostAPIError(
                f"Unsafe duplicate OpenPost publications detected for SocialMarket job {job_id} / {platform}"
            )
        return matches[0] if matches else None

    @staticmethod
    def _publication_external_url(publication: dict[str, Any]) -> str:
        for rendition in publication.get("renditions") or []:
            if not isinstance(rendition, dict):
                continue
            url = str(rendition.get("external_url") or "").strip()
            if url:
                return url
            delivery = rendition.get("delivery") if isinstance(rendition.get("delivery"), dict) else {}
            url = str(delivery.get("external_url") or "").strip()
            if url:
                return url
        return ""

    @staticmethod
    def _safe_state(publication: dict[str, Any]) -> str:
        return str(publication.get("status") or "").strip().lower()

    def _download_media(self, media_url: str) -> tuple[bytes, str, str, str]:
        request = urllib.request.Request(
            media_url,
            headers={"User-Agent": "socialscheduler-openpost/1.0", "Accept": "*/*"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                declared = response.headers.get("Content-Length")
                if declared and int(declared) > self.media_max_bytes:
                    raise OpenPostAPIError(
                        f"Media exceeds OPENPOST_MEDIA_MAX_BYTES ({declared} > {self.media_max_bytes})"
                    )
                chunks: list[bytes] = []
                size = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > self.media_max_bytes:
                        raise OpenPostAPIError(
                            f"Media exceeds OPENPOST_MEDIA_MAX_BYTES ({size} > {self.media_max_bytes})"
                        )
                    chunks.append(chunk)
                content = b"".join(chunks)
                mime_type = str(response.headers.get("Content-Type") or "").split(";", 1)[0].strip()
        except OpenPostAPIError:
            raise
        except Exception as exc:
            raise OpenPostAPIError(f"Unable to download approved media_url: {exc}") from exc
        if not content:
            raise OpenPostAPIError("Approved media_url returned an empty body")
        filename = urllib.parse.unquote(os.path.basename(urllib.parse.urlsplit(media_url).path)) or "socialmarket-media"
        mime_type = mime_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        digest = hashlib.sha256(content).hexdigest()
        return content, filename, mime_type, digest

    def _upload_binary(self, target: dict[str, Any], content: bytes, mime_type: str) -> None:
        target_url_raw = str(target.get("url") or "").strip()
        if not target_url_raw:
            raise OpenPostAPIError("OpenPost media upload session returned no upload URL")
        target_url = self._absolute_url(target_url_raw)
        method = str(target.get("method") or "PUT").strip().upper()
        headers = {str(key): str(value) for key, value in dict(target.get("headers") or {}).items()}
        headers.setdefault("Content-Type", mime_type)
        headers.setdefault("Content-Length", str(len(content)))
        api_host = urllib.parse.urlsplit(self.api_url).netloc
        target_host = urllib.parse.urlsplit(target_url).netloc
        if target_host == api_host and not any(key.lower() == "authorization" for key in headers):
            headers["Authorization"] = f"Bearer {self.api_token}"
        request = urllib.request.Request(target_url, data=content, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=max(self.timeout_seconds, 60)) as response:
                response.read()
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:2000]
            except Exception:
                pass
            raise OpenPostAPIError(
                f"OpenPost media upload HTTP {exc.code}: {detail or exc.reason}",
                status_code=exc.code,
            ) from exc
        except Exception as exc:
            raise OpenPostAPIError(f"OpenPost media upload failed: {exc}", ambiguous=True) from exc

    def _wait_media_ready(self, media_id: str) -> None:
        if self.media_ready_timeout_seconds <= 0:
            return
        deadline = time.monotonic() + self.media_ready_timeout_seconds
        while True:
            result = self._request_json(
                "GET",
                "/media",
                query={
                    "workspace_id": self.workspace_id,
                    "lifecycle": "all",
                    "asset_kind": "all",
                    "limit": 200,
                },
            )
            rows = list((result or {}).get("media") or []) if isinstance(result, dict) else []
            match = next((row for row in rows if isinstance(row, dict) and str(row.get("id") or "") == media_id), None)
            if match:
                state = str(match.get("processing_status") or "").strip().lower()
                if state in {"ready", "completed", "complete"}:
                    return
                if state == "failed":
                    raise OpenPostAPIError(
                        f"OpenPost media processing failed for {media_id}: {match.get('analysis_error') or 'unknown error'}"
                    )
            if time.monotonic() >= deadline:
                raise OpenPostAPIError(f"OpenPost media {media_id} did not become ready before timeout")
            time.sleep(2)

    def upload_from_url(self, media_url: str) -> str:
        content, filename, mime_type, digest = self._download_media(media_url)
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

    def create_publication(self, job: dict[str, Any], account_id: str) -> dict[str, Any]:
        job_id = str(job.get("id") or "").strip()
        platform = str(job.get("platform") or "").strip().lower()
        scheduled_for = str(job.get("scheduled_for") or "").strip()
        if not job_id or platform not in SERVICES or not scheduled_for:
            raise OpenPostAPIError("OpenPost job requires id, supported platform and scheduled_for")
        content = _render_content(job)
        if not content:
            raise OpenPostAPIError("OpenPost job has no publishable content")
        profile = _content_profile(platform, str(job.get("format") or ""))
        media_url = str(job.get("media_url") or "").strip()
        media: list[dict[str, Any]] = []
        if media_url:
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
                "tracking_url": str(job.get("tracking_url") or "").strip(),
            },
            "social_account_ids": [account_id],
            "media": media,
        }
        result = self._request_json("POST", "/publications", payload, write=True)
        if not isinstance(result, dict) or not result.get("id") or not result.get("revision"):
            raise OpenPostAPIError("OpenPost create-publication returned no id/revision", ambiguous=True)
        return dict(result)

    def schedule_publication(self, publication_id: str, revision: int) -> dict[str, Any]:
        result = self._request_json(
            "POST",
            f"/publications/{urllib.parse.quote(publication_id, safe='')}/schedule",
            {"expected_revision": int(revision), "execution_intent": "production"},
            write=True,
        )
        return dict(result or {}) if isinstance(result, dict) else {}

    def schedule_job(self, job: dict[str, Any], account_id: str) -> dict[str, Any]:
        job_id = str(job.get("id") or "").strip()
        platform = str(job.get("platform") or "").strip().lower()
        existing = self.find_job_publication(job_id, platform)
        publication: dict[str, Any]
        reconciled = existing is not None
        if existing is not None:
            state = self._safe_state(existing)
            if state in {"scheduled", "queued", "publishing", "published", "sent"}:
                return {
                    "publicationId": str(existing.get("id") or ""),
                    "postId": str(existing.get("id") or ""),
                    "status": state,
                    "scheduledAt": str(existing.get("scheduled_at") or job.get("scheduled_for") or ""),
                    "externalUrl": self._publication_external_url(existing),
                    "reconciled": True,
                }
            if state not in {"", "draft"}:
                raise OpenPostAPIError(
                    f"Existing OpenPost publication for job {job_id} is in unsafe state {state}; refusing duplicate create"
                )
            publication = existing
        else:
            try:
                publication = self.create_publication(job, account_id)
            except OpenPostAPIError as exc:
                if not exc.ambiguous:
                    raise
                publication = self.find_job_publication(job_id, platform) or {}
                if not publication:
                    raise
                reconciled = True

        publication_id = str(publication.get("id") or "").strip()
        revision = int(publication.get("revision") or 0)
        if not publication_id or revision <= 0:
            raise OpenPostAPIError("OpenPost publication is missing id/revision; refusing schedule mutation")
        try:
            self.schedule_publication(publication_id, revision)
        except OpenPostAPIError as exc:
            if not exc.ambiguous:
                raise
            current = self.get_publication(publication_id)
            state = self._safe_state(current)
            if state not in {"scheduled", "queued", "publishing", "published", "sent"}:
                raise
            publication = current
            reconciled = True
        return {
            "publicationId": publication_id,
            "postId": publication_id,
            "status": "scheduled",
            "scheduledAt": str(publication.get("scheduled_at") or job.get("scheduled_for") or ""),
            "externalUrl": self._publication_external_url(publication),
            "reconciled": reconciled,
        }
