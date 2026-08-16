from __future__ import annotations

import json
import os
from datetime import datetime

from src.buffer_client import BufferAPIError, BufferClient

START = datetime.fromisoformat(os.getenv("PURGE_START", "2026-08-17T21:00:00+00:00"))
END = datetime.fromisoformat(os.getenv("PURGE_END", "2026-11-30T22:00:00+00:00"))


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def delete_post(client: BufferClient, post_id: str) -> dict:
    query = """
    mutation DeletePost($input: DeletePostInput!) {
      deletePost(input: $input) {
        ... on DeletePostSuccess { id }
        ... on MutationError { message }
      }
    }
    """
    result = client.execute(query, {"input": {"id": post_id}})["deletePost"]
    if result.get("message"):
        raise BufferAPIError(f"deletePost failed for {post_id}: {result['message']}")
    return result


def main() -> int:
    org_id = os.environ["BUFFER_ORGANIZATION_ID"]
    client = BufferClient.from_env()
    posts = client.posts(org_id, ["scheduled"])
    candidates = []
    for post in posts:
        due = parse_dt(post.get("dueAt"))
        if not due or not (START <= due < END):
            continue
        # Legacy scheduler created durable Buffer Ideas. SocialMarket outbox mode does not.
        if not post.get("ideaId"):
            continue
        candidates.append(post)

    deleted = []
    for post in candidates:
        delete_post(client, str(post["id"]))
        deleted.append({"id": post["id"], "dueAt": post.get("dueAt"), "ideaId": post.get("ideaId")})

    print(json.dumps({
        "ok": True,
        "window": {"start": START.isoformat(), "end": END.isoformat()},
        "scheduled_seen": len(posts),
        "legacy_candidates": len(candidates),
        "deleted": deleted,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
