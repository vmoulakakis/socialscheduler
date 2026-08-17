from __future__ import annotations

import json
import mimetypes
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any


class BrightBeanAPIError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _compose_caption(job: dict[str, Any]) -> str:
    caption = str(job.get("caption") or "").strip()
    hashtags = [str(tag).strip() for tag in (job.get("hashtags") or []) if str(tag).strip()]
    extras = [tag for tag in hashtags if tag not in caption]
    if extras:
        caption = f"{caption}\n\n{' '.join(extras)}".strip()
    tracking_url = str(job.get("tracking_url") or "").strip()
    if tracking_url and tracking_url not in caption:
        caption = f"{caption}\n\n{tracking_url}".strip()
    return caption


@dataclass
class BrightBeanClient:
    api_url: str
    api_key: str
    timeout_seconds: int = 30
    media_max_bytes: int = 25 * 1024 * 1024

    @classmethod
    def from_env(cls) -> "BrightBeanClient":
        api_url = os.getenv("BRIGHTBEAN_API_URL", "https://studio.brightbean.xyz/api/v1").strip().rstrip("/")
        api_key = os.getenv("BRIGHTBEAN_API_KEY", "").strip()
        if not api_key:
            raise BrightBeanAPIError("BRIGHTBEAN_API_KEY is required")
        return cls(
            api_url=api_url,
            api_key=api_key,
            timeout_seconds=int(os.getenv("BRIGHTBEAN_TIMEOUT_SECONDS", "30")),
            media_max_bytes=int(os.getenv("BRIGHTBEAN_MEDIA_MAX_BYTES", str(25 * 1024 * 1024))),
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        body: bytes | None = None,
        content_type: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        url = f"{self.api_url}/{path.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "User-Agent": "socialscheduler/brightbean-1.0",
        }
        data = body
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            content_type = "application/json"
        if content_type:
            headers["Content-Type"] = content_type
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key[:128]
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
            raise BrightBeanAPIError(
                f"BrightBean HTTP {exc.code}: {detail or exc.reason}",
                status_code=exc.code,
            ) from exc
        except Exception as exc:
            raise BrightBeanAPIError(f"BrightBean request failed: {exc}") from exc

    def me(self) -> dict[str, Any]:
        return self._request("GET", "me")

    def list_accounts(self) -> list[dict[str, Any]]:
        result = self._request("GET", "accounts")
        return list(result.get("accounts") or [])

    def resolve_account(self, route_platform: str) -> dict[str, Any]:
        route_platform = route_platform.strip().lower()
        env_name = f"BRIGHTBEAN_ACCOUNT_{route_platform.upper()}"
        configured_id = os.getenv(env_name, "").strip()
        accounts = [a for a in self.list_accounts() if str(a.get("connection_status") or "").lower() == "connected"]

        if route_platform == "linkedin":
            candidates = [a for a in accounts if str(a.get("platform") or "").lower() in {"linkedin_personal", "linkedin_company"}]
        else:
            candidates = [a for a in accounts if str(a.get("platform") or "").lower() == route_platform]

        if configured_id:
            for account in candidates:
                if str(account.get("id") or "") == configured_id:
                    return account
            raise BrightBeanAPIError(f"{env_name} does not match a connected allowlisted BrightBean account")

        if len(candidates) == 1:
            return candidates[0]
        if not candidates:
            raise BrightBeanAPIError(f"No connected BrightBean account is available for route '{route_platform}'")
        raise BrightBeanAPIError(
            f"Multiple BrightBean accounts match '{route_platform}'; set {env_name} to the intended account UUID"
        )

    def _download_media(self, media_url: str) -> tuple[bytes, str, str]:
        parsed = urllib.parse.urlsplit(media_url)
        if parsed.scheme not in {"http", "https"}:
            raise BrightBeanAPIError("BrightBean media URL must use http or https")
        req = urllib.request.Request(media_url, headers={"User-Agent": "socialscheduler/brightbean-1.0"}, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                content_type = (response.headers.get_content_type() or "application/octet-stream").lower()
                filename = os.path.basename(urllib.parse.unquote(parsed.path)) or "socialmarket-media"
                if "." not in filename:
                    ext = mimetypes.guess_extension(content_type) or ""
                    filename += ext
                data = response.read(self.media_max_bytes + 1)
        except Exception as exc:
            raise BrightBeanAPIError(f"Unable to download SocialMarket media: {exc}") from exc
        if len(data) > self.media_max_bytes:
            raise BrightBeanAPIError(f"Media exceeds BRIGHTBEAN_MEDIA_MAX_BYTES={self.media_max_bytes}")
        return data, filename, content_type

    def upload_media_url(self, media_url: str, *, job_id: str) -> str:
        data, filename, mime_type = self._download_media(media_url)
        boundary = f"----socialscheduler-{uuid.uuid4().hex}"
        chunks: list[bytes] = []

        def add_field(name: str, value: str) -> None:
            chunks.extend([
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                value.encode("utf-8"),
                b"\r\n",
            ])

        add_field("idempotency_key", f"socialscheduler-media-{job_id}")
        chunks.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode(),
            f"Content-Type: {mime_type}\r\n\r\n".encode(),
            data,
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ])
        result = self._request(
            "POST",
            "media/",
            body=b"".join(chunks),
            content_type=f"multipart/form-data; boundary={boundary}",
            idempotency_key=f"socialscheduler-media-{job_id}",
        )
        media_id = str(result.get("id") or "").strip()
        if not media_id:
            raise BrightBeanAPIError("BrightBean media upload response did not include an id")
        return media_id

    def schedule_job(self, job: dict[str, Any], account: dict[str, Any]) -> dict[str, Any]:
        job_id = str(job.get("id") or "").strip()
        scheduled_for = str(job.get("scheduled_for") or "").strip()
        if not job_id or not scheduled_for:
            raise BrightBeanAPIError("SocialMarket job is missing id or scheduled_for")

        caption = _compose_caption(job)
        if not caption:
            raise BrightBeanAPIError("SocialMarket job caption is empty")

        char_limit = int(account.get("char_limit") or 10000)
        escaped_chars = str(account.get("escaped_chars") or "")
        effective_length = len(caption) + sum(caption.count(ch) for ch in escaped_chars)
        if effective_length > char_limit:
            raise BrightBeanAPIError(
                f"Caption length {effective_length} exceeds BrightBean account limit {char_limit}",
                status_code=422,
            )

        media_asset_ids: list[str] = []
        media_url = str(job.get("media_url") or "").strip()
        if media_url:
            media_asset_ids.append(self.upload_media_url(media_url, job_id=job_id))

        payload: dict[str, Any] = {
            "social_account_id": str(account.get("id") or ""),
            "caption": caption,
            "title": str(job.get("title") or "") if account.get("needs_title") else "",
            "media_asset_ids": media_asset_ids,
            "action": "schedule",
            "scheduled_at": scheduled_for,
            "idempotency_key": f"socialscheduler-{job_id}-{account.get('id')}",
        }
        return self._request(
            "POST",
            "posts/",
            payload=payload,
            idempotency_key=payload["idempotency_key"],
        )
