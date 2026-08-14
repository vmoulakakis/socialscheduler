from __future__ import annotations

import json
import os
from collections import Counter

from src.buffer_client import BufferClient, BufferAPIError

ORG_ID = os.getenv("BUFFER_ORGANIZATION_ID", "68a86463018d512de98d6315").strip()
STATUSES = ["draft", "needs_approval", "scheduled", "sending", "sent", "error"]
TRAVEL_AI_IDEA = "6a7f0383153244db8c91ef2a"


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
    travel_idea = next((idea for idea in ideas if idea.get("id") == TRAVEL_AI_IDEA), None)
    travel_posts = [post for post in posts if post.get("ideaId") == TRAVEL_AI_IDEA]

    summary = {
        "ok": True,
        "organization": {"id": ORG_ID, "name": orgs[ORG_ID]},
        "channel_count": len(channels),
        "channels": [
            {"id": c.get("id"), "name": c.get("name"), "service": c.get("service")}
            for c in channels
        ],
        "post_count": len(posts),
        "status_counts": dict(status_counts),
        "active_queue": len(active),
        "active_queue_limit": 10,
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
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BufferAPIError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        raise SystemExit(2)
