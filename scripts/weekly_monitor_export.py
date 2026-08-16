from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from src.buffer_client import BufferClient

ATHENS = ZoneInfo("Europe/Athens")
ORG_ID = os.getenv("BUFFER_ORGANIZATION_ID", "68a86463018d512de98d6315").strip()
OUT = Path(os.getenv("MONITOR_EXPORT_PATH", "artifacts/buffer-week.json"))


def parse_dt(value):
    if not value:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def in_window(value, start_utc, end_utc):
    dt = parse_dt(value)
    return bool(dt and start_utc <= dt < end_utc)


def completed_week_window():
    override = os.getenv("REPORT_WEEK_START", "").strip()
    now_local = datetime.now(ATHENS)
    if override:
        start_date = datetime.fromisoformat(override).date()
    else:
        this_monday = now_local.date() - timedelta(days=now_local.weekday())
        start_date = this_monday - timedelta(days=7)
    end_date = start_date + timedelta(days=7)
    start_local = datetime.combine(start_date, time.min, tzinfo=ATHENS)
    end_local = datetime.combine(end_date, time.min, tzinfo=ATHENS)
    return start_local, end_local


def main() -> int:
    start_local, end_local = completed_week_window()
    start_utc, end_utc = start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)
    client = BufferClient.from_env()

    snapshot = client.runtime_snapshot(ORG_ID)
    channel_map = {str(row.get("id")): str(row.get("service") or "unknown") for row in snapshot.get("channels", [])}

    sent_all = client.sent_posts_with_metrics(ORG_ID, page_size=100, max_pages=12)
    sent = []
    for post in sent_all:
        event_time = post.get("sentAt") or post.get("dueAt")
        if not in_window(event_time, start_utc, end_utc):
            continue
        sent.append({
            "buffer_post_id": post.get("id"),
            "channel_id": post.get("channelId"),
            "channel": post.get("channelService") or channel_map.get(str(post.get("channelId")), "unknown"),
            "status": post.get("status"),
            "due_at": post.get("dueAt"),
            "sent_at": post.get("sentAt"),
            "external_link": post.get("externalLink"),
            "text": post.get("text"),
            "metrics": post.get("metrics") or [],
            "metrics_updated_at": post.get("metricsUpdatedAt"),
        })

    active = []
    for post in snapshot.get("posts", []):
        active.append({
            "buffer_post_id": post.get("id"),
            "channel_id": post.get("channelId"),
            "channel": post.get("channelService") or channel_map.get(str(post.get("channelId")), "unknown"),
            "status": post.get("status"),
            "due_at": post.get("dueAt"),
            "text": post.get("text"),
            "external_link": post.get("externalLink"),
            "source": "current_buffer_runtime_snapshot",
        })

    errors_all = client.posts(ORG_ID, ["error"])
    errors = []
    for post in errors_all:
        if not any(in_window(post.get(field), start_utc, end_utc) for field in ("dueAt", "createdAt", "updatedAt")):
            continue
        errors.append({
            "buffer_post_id": post.get("id"),
            "channel_id": post.get("channelId"),
            "channel": post.get("channelService") or channel_map.get(str(post.get("channelId")), "unknown"),
            "status": post.get("status"),
            "due_at": post.get("dueAt"),
            "created_at": post.get("createdAt"),
            "updated_at": post.get("updatedAt"),
            "text": post.get("text"),
            "external_link": post.get("externalLink"),
        })

    sent_by_channel = Counter(row["channel"] for row in sent)
    active_by_channel = Counter(row["channel"] for row in active)
    metrics_rows = sum(1 for row in sent if row.get("metrics"))

    payload = {
        "ok": True,
        "generated_at": datetime.now(ATHENS).isoformat(timespec="seconds"),
        "timezone": "Europe/Athens",
        "week_start": start_local.isoformat(),
        "week_end_exclusive": end_local.isoformat(),
        "organization_id": ORG_ID,
        "channels": snapshot.get("channels") or [],
        "summary": {
            "sent_posts": len(sent),
            "sent_by_channel": dict(sent_by_channel),
            "sent_with_metrics": metrics_rows,
            "current_active_queue": len(active),
            "current_active_by_channel": dict(active_by_channel),
            "errors_in_week": len(errors),
        },
        "sent_posts": sorted(sent, key=lambda row: str(row.get("sent_at") or row.get("due_at") or "")),
        "current_active_posts": sorted(active, key=lambda row: str(row.get("due_at") or "")),
        "errors": sorted(errors, key=lambda row: str(row.get("due_at") or row.get("created_at") or "")),
        "truth_notes": [
            "sent_posts are read directly from Buffer with status=sent and filtered to the completed Athens week",
            "current_active_posts are read directly from the live Buffer scheduled/sending snapshot at export time",
            "errors are read directly from Buffer error posts and filtered to the weekly window",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
