from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from src.buffer_client import BufferAPIError, BufferClient
from src.socialmarket_outbox import SocialMarketOutboxClient, SocialMarketOutboxError


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    organization_id = os.getenv("BUFFER_ORGANIZATION_ID", "").strip()
    if not organization_id:
        print(json.dumps({"ok": False, "error": "BUFFER_ORGANIZATION_ID is required"}, ensure_ascii=False))
        return 2

    try:
        buffer = BufferClient.from_env()
        outbox = SocialMarketOutboxClient.from_env()
        posts = buffer.sent_posts_with_metrics(organization_id, page_size=100, max_pages=5)
        rows = []
        for post in posts:
            post_id = str(post.get("id") or "").strip()
            if not post_id:
                continue
            metrics = post.get("metrics") if isinstance(post.get("metrics"), list) else []
            rows.append({
                "buffer_post_id": post_id,
                "status": str(post.get("status") or ""),
                "sent_at": post.get("sentAt"),
                "external_link": post.get("externalLink"),
                "metrics": metrics,
                "metrics_updated_at": post.get("metricsUpdatedAt") or _iso_now(),
            })

        result = outbox.metrics_batch(rows) if rows else {"updated": 0, "missing": 0}
        with_metrics = sum(1 for row in rows if row.get("metrics"))
        payload = {
            "ok": True,
            "buffer_sent_posts_scanned": len(rows),
            "posts_with_metrics": with_metrics,
            "database": result,
            "synced_at": _iso_now(),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    except (BufferAPIError, SocialMarketOutboxError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc), "synced_at": _iso_now()}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
