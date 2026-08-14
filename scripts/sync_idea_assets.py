from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from src.buffer_client import BufferAPIError, BufferClient, BufferRateLimitError

ROOT = Path(__file__).resolve().parents[1]
BACKLOG = ROOT / "config" / "backlog.json"
ASSETS = ROOT / "assets"
MAX_BYTES = 25 * 1024 * 1024


def load_backlog() -> list[dict]:
    with BACKLOG.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def download(url: str, destination: Path) -> bool:
    request = urllib.request.Request(url, headers={"User-Agent": "socialscheduler/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            content_type = (response.headers.get("Content-Type") or "").lower()
            if content_type and not (content_type.startswith("image/") or content_type == "application/octet-stream"):
                print(f"skip {destination.name}: unexpected content type {content_type}")
                return False
            length = response.headers.get("Content-Length")
            if length and int(length) > MAX_BYTES:
                print(f"skip {destination.name}: media exceeds {MAX_BYTES} bytes")
                return False
            data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                print(f"skip {destination.name}: media exceeds {MAX_BYTES} bytes")
                return False
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
        print(f"skip {destination.name}: download failed: {exc}")
        return False

    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_suffix(destination.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(destination)
    return True


def main() -> int:
    org_id = os.getenv("BUFFER_ORGANIZATION_ID", "68a86463018d512de98d6315").strip()
    client = BufferClient.from_env()
    ideas = client.ideas(org_id)
    by_id = {idea.get("id"): idea for idea in ideas if idea.get("id")}

    downloaded = 0
    missing = 0
    for item in load_backlog():
        filename = item.get("asset_filename")
        idea_id = item.get("idea_id")
        if not filename or not idea_id:
            continue
        destination = ASSETS / filename
        if destination.exists() and destination.stat().st_size > 0:
            continue
        idea = by_id.get(idea_id)
        media = ((idea or {}).get("content") or {}).get("media") or []
        image = next((m for m in media if m.get("type") in {"image", "gif"} and m.get("url")), None)
        if not image:
            print(f"missing media in Idea {idea_id} for {filename}")
            missing += 1
            continue
        if download(image["url"], destination):
            print(f"synced {filename} from Buffer Idea {idea_id}")
            downloaded += 1
        else:
            missing += 1

    print(json.dumps({"status": "completed", "downloaded": downloaded, "missing": missing}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BufferRateLimitError as exc:
        print(json.dumps({
            "status": "rate_limited",
            "retry_after_seconds": exc.retry_after_seconds,
            "action": "defer_without_writes",
        }, indent=2))
        raise SystemExit(0)
    except BufferAPIError as exc:
        print(f"Buffer asset sync failed: {exc}")
        raise SystemExit(2)
