from __future__ import annotations

import json
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from src.buffer_client import BufferClient
from src.socialmarket_outbox import SocialMarketOutboxClient

ATHENS = ZoneInfo("Europe/Athens")
ORG_ID = "68a86463018d512de98d6315"


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def main() -> int:
    now_local = datetime.now(ATHENS)
    this_monday = now_local.date() - timedelta(days=now_local.weekday())
    week_start_date = this_monday - timedelta(days=7)
    week_end_date = this_monday
    start_local = datetime.combine(week_start_date, time.min, tzinfo=ATHENS)
    end_local = datetime.combine(week_end_date, time.min, tzinfo=ATHENS)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)

    buffer = BufferClient.from_env()
    outbox = SocialMarketOutboxClient.from_env()

    # At 300/week, 8 pages is deliberately above the expected requirement and
    # still tiny compared with hourly polling. Sort is newest-first.
    posts = buffer.sent_posts_with_metrics(ORG_ID, page_size=100, max_pages=8)
    selected: list[dict] = []
    for post in posts:
        sent_raw = post.get("sentAt") or post.get("dueAt")
        if not sent_raw:
            continue
        sent = datetime.fromisoformat(str(sent_raw).replace("Z", "+00:00"))
        if sent < start_utc:
            continue
        if sent >= end_utc:
            continue
        selected.append({
            "buffer_post_id": post.get("id"),
            "status": post.get("status"),
            "sent_at": post.get("sentAt"),
            "external_link": post.get("externalLink"),
            "metrics": post.get("metrics") or [],
            "metrics_updated_at": post.get("metricsUpdatedAt"),
        })

    metric_results: list[dict] = []
    for start in range(0, len(selected), 400):
        metric_results.append(outbox.metrics_batch(selected[start:start + 400]))

    decision = outbox.optimize_week(week_start_date.isoformat())
    print(json.dumps({
        "ok": True,
        "week_start": week_start_date.isoformat(),
        "week_end": week_end_date.isoformat(),
        "buffer_sent_posts_scanned": len(posts),
        "weekly_posts_selected": len(selected),
        "metric_batches": metric_results,
        "optimizer": decision,
        "window_utc": {"start": _iso(start_utc), "end": _iso(end_utc)},
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
