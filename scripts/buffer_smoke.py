from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timedelta, timezone

from src.buffer_client import BufferAPIError, BufferClient, BufferRateLimitError

ORG_ID = os.getenv("BUFFER_ORGANIZATION_ID", "68a86463018d512de98d6315").strip()
STATUSES = ["draft", "needs_approval", "scheduled", "sending", "sent", "error"]
TRAVEL_AI_IDEA = "6a7f0383153244db8c91ef2a"
PER_CHANNEL_LIMIT = 10


def set_output(name: str, value: str) -> None:
    path = os.getenv("GITHUB_OUTPUT", "").strip()
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"{name}={value}\n")


def main() -> int:
    client = BufferClient.from_env()
    account = client.account()
    orgs = {org.get("id"): org.get("name") for org in account.get("organizations", [])}
    if ORG_ID not in orgs:
        raise BufferAPIError(f"organization {ORG_ID} not accessible")

    channels = client.channels(ORG_ID)
    posts = client.posts(ORG_ID, STATUSES)
    ideas = client.ideas(ORG_ID)

    status_counts = Counter(post.get("status") for post in posts)
    active = [post for post in posts if post.get("status") in {"scheduled", "sending"}]
    channel_queue = []
    for channel in channels:
        channel_id = channel.get("id")
        channel_active = sum(1 for post in active if post.get("channelId") == channel_id)
        channel_queue.append({
            "id": channel_id,
            "name": channel.get("name"),
            "service": channel.get("service"),
            "active_queue": channel_active,
            "queue_limit": PER_CHANNEL_LIMIT,
            "missing_slots": max(0, PER_CHANNEL_LIMIT - channel_active),
            "fill_rate_pct": min(100.0, round(channel_active * 100.0 / PER_CHANNEL_LIMIT, 2)),
        })

    travel_idea = next((idea for idea in ideas if idea.get("id") == TRAVEL_AI_IDEA), None)
    travel_posts = [post for post in posts if post.get("ideaId") == TRAVEL_AI_IDEA]
    total_limit = PER_CHANNEL_LIMIT * len(channels)

    summary = {
        "ok": True,
        "status": "available",
        "organization": {"id": ORG_ID, "name": orgs[ORG_ID]},
        "channel_count": len(channels),
        "channels": [
            {"id": c.get("id"), "name": c.get("name"), "service": c.get("service")}
            for c in channels
        ],
        "channel_queue": channel_queue,
        "post_count": len(posts),
        "status_counts": dict(status_counts),
        "active_queue": len(active),
        "active_queue_limit": total_limit,
        "fill_rate_pct": min(100.0, round(len(active) * 100.0 / max(1, total_limit), 2)),
        "ideas_count": len(ideas),
        "travel_ai_sep12_idea_found": bool(travel_idea),
        "travel_ai_sep12_posts": [
            {
                "id": p.get("id"),
                "status": p.get("status"),
                "channelId": p.get("channelId"),
                "dueAt": p.get("dueAt"),
                "shareMode": p.get("shareMode"),
            }
            for p in travel_posts
        ],
        "errors": [
            {"id": p.get("id"), "channelId": p.get("channelId"), "ideaId": p.get("ideaId")}
            for p in posts if p.get("status") == "error"
        ],
    }
    set_output("available", "true")
    set_output("status", "available")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BufferRateLimitError as exc:
        retry_at = None
        if exc.retry_after_seconds is not None:
            retry_at = datetime.now(timezone.utc) + timedelta(seconds=exc.retry_after_seconds)
        set_output("available", "false")
        set_output("status", "rate_limited")
        if retry_at is not None:
            set_output("retry_at_utc", retry_at.isoformat(timespec="seconds"))
        print(json.dumps({
            "ok": True,
            "status": "rate_limited",
            "retry_after_seconds": exc.retry_after_seconds,
            "retry_at_utc": retry_at.isoformat(timespec="seconds") if retry_at else None,
            "action": "defer_without_writes",
        }, ensure_ascii=False, indent=2))
        raise SystemExit(0)
    except BufferAPIError as exc:
        set_output("available", "false")
        set_output("status", "error")
        print(json.dumps({"ok": False, "status": "error", "error": str(exc)}, ensure_ascii=False, indent=2))
        raise SystemExit(2)
