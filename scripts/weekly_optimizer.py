from __future__ import annotations

import json
import os
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from src.buffer_client import BufferClient
from src.socialmarket_outbox import SocialMarketOutboxClient

ATHENS = ZoneInfo("Europe/Athens")
ORG_ID = os.getenv("BUFFER_ORGANIZATION_ID", "68a86463018d512de98d6315")
PROVIDERS = ("buffer", "postzen", "brightbean")


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

    outbox = SocialMarketOutboxClient.from_env()
    health = {
        "buffer": {"configured": bool(os.getenv("BUFFER_API_KEY")), "engagement_metrics": "available"},
        "postzen": {"configured": bool(os.getenv("POSTZEN_API_KEY")), "engagement_metrics": "provider_ack"},
        "brightbean": {"configured": bool(os.getenv("BRIGHTBEAN_API_KEY")), "engagement_metrics": "provider_ack"},
    }

    selected: list[dict] = []
    scanned = 0
    metric_results: list[dict] = []
    if health["buffer"]["configured"]:
        buffer = BufferClient.from_env()
        posts = buffer.sent_posts_with_metrics(ORG_ID, page_size=100, max_pages=8)
        scanned = len(posts)
        for post in posts:
            sent_raw = post.get("sentAt") or post.get("dueAt")
            if not sent_raw:
                continue
            sent = datetime.fromisoformat(str(sent_raw).replace("Z", "+00:00"))
            if start_utc <= sent < end_utc:
                selected.append({
                    "buffer_post_id": post.get("id"),
                    "status": post.get("status"),
                    "sent_at": post.get("sentAt"),
                    "external_link": post.get("externalLink"),
                    "metrics": post.get("metrics") or [],
                    "metrics_updated_at": post.get("metricsUpdatedAt"),
                })
        for start in range(0, len(selected), 400):
            metric_results.append(outbox.metrics_batch(selected[start:start + 400]))

    # Canonical optimizer reads delivery acknowledgements from the shared outbox.
    # PostZen/BrightBean therefore affect reliability/routing; Buffer additionally
    # contributes post-level engagement metrics when its API exposes them.
    decision = outbox.optimize_week(week_start_date.isoformat())
    report = {
        "ok": True,
        "objective": "conversion_first_organic_growth",
        "week_start": week_start_date.isoformat(),
        "week_end": week_end_date.isoformat(),
        "health": health,
        "providers": list(PROVIDERS),
        "buffer_sent_posts_scanned": scanned,
        "buffer_weekly_posts_selected": len(selected),
        "metric_batches": metric_results,
        "optimizer": decision,
        "window_utc": {"start": _iso(start_utc), "end": _iso(end_utc)},
        "rules": {"missing_metrics": "UNKNOWN", "deduplicate": True, "provider_ack_required": True},
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
