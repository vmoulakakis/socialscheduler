from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path

from .buffer_client import BufferAPIError, BufferClient, BufferRateLimitError
from .scheduler import ACTIVE_QUEUE_STATUSES, load_json
from .scheduler_v2 import SocialScheduler
from .socialmarket_outbox import SocialMarketOutboxClient, SocialMarketOutboxError, jobs_to_backlog

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ("facebook", "instagram", "tiktok")


def main() -> int:
    parser = argparse.ArgumentParser(description="Conversion-first rolling Buffer social scheduler")
    parser.add_argument("--mode", choices=["live", "dry-run"], default=os.getenv("SCHEDULER_MODE", "dry-run"))
    parser.add_argument("--settings", default=str(ROOT / "config" / "settings.json"))
    parser.add_argument("--channels", default=str(ROOT / "config" / "channels.json"))
    parser.add_argument("--backlog", default=str(ROOT / "config" / "backlog.json"))
    args = parser.parse_args()

    settings = load_json(args.settings)
    channels = load_json(args.channels)
    env_org = os.getenv("BUFFER_ORGANIZATION_ID", "").strip()
    if env_org:
        settings["organization_id"] = env_org

    client = BufferClient.from_env()
    content_source = os.getenv("CONTENT_SOURCE", "socialmarket_outbox").strip() or "socialmarket_outbox"
    outbox: SocialMarketOutboxClient | None = None
    snapshot: dict | None = None
    refill_result: dict = {}
    capacity: dict[str, int] = {service: 0 for service in SERVICES}

    try:
        if content_source == "socialmarket_outbox":
            outbox = SocialMarketOutboxClient.from_env()
            settings["content_source"] = "socialmarket_outbox"
            if args.mode == "live":
                try:
                    # Exactly one Buffer read for this hourly run. The same snapshot is
                    # passed into the scheduler after the outbox claim.
                    snapshot = client.runtime_snapshot(settings["organization_id"])
                except BufferRateLimitError as exc:
                    print(json.dumps({
                        "ok": True,
                        "status": "rate_limited",
                        "retry_after_seconds": exc.retry_after_seconds,
                        "action": "defer_without_outbox_claim",
                    }, ensure_ascii=False, indent=2))
                    return 0
                except BufferAPIError as exc:
                    print(json.dumps({"ok": False, "status": "error", "error": str(exc)}, ensure_ascii=False, indent=2))
                    return 2

                if snapshot.get("has_next_page"):
                    raise BufferAPIError("Unsafe active-queue pagination state; refusing capacity claim")
                active_by_channel = Counter(
                    str(post.get("channelId") or "")
                    for post in snapshot.get("posts", [])
                    if post.get("status") in ACTIVE_QUEUE_STATUSES
                )
                per_channel_limit = int(settings.get("queue_limit_per_channel", settings.get("queue_limit", 10)))
                for service in SERVICES:
                    channel_id = str((channels.get(service) or {}).get("id") or "")
                    capacity[service] = max(0, per_channel_limit - int(active_by_channel.get(channel_id, 0)))

                # SocialMarket keeps a short rolling planning horizon in Supabase. Rows
                # are removed from the live outbox immediately after Buffer accepts them.
                refill_result = outbox.refill(int(settings.get("outbox_horizon_hours", 72)))
                jobs = outbox.claim_capacity(capacity)
                settings["preclaim_capacity"] = capacity
                settings["preclaim_active_queue"] = sum(active_by_channel.values())
            else:
                jobs = outbox.peek(int(settings.get("max_creates_per_run", 30)))
            backlog = jobs_to_backlog(jobs)
        elif content_source == "legacy_backlog":
            backlog = load_json(args.backlog)
            settings["content_source"] = "legacy_backlog"
        else:
            raise SocialMarketOutboxError(f"Unsupported CONTENT_SOURCE={content_source}")
    except (SocialMarketOutboxError, BufferAPIError) as exc:
        print(json.dumps({"ok": False, "status": "outbox_error", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 3

    scheduler = SocialScheduler(client=client, settings=settings, channels=channels, backlog=backlog, mode=args.mode)
    if snapshot is not None:
        scheduler.runtime_snapshot = snapshot
    try:
        result = scheduler.run()
    except BufferRateLimitError as exc:
        print(json.dumps({
            "ok": True,
            "status": "rate_limited",
            "retry_after_seconds": exc.retry_after_seconds,
            "action": "leases_expire_without_duplicate_creation",
        }, ensure_ascii=False, indent=2))
        return 0
    except BufferAPIError as exc:
        print(json.dumps({"ok": False, "status": "error", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    if settings.get("preclaim_capacity") is not None:
        result["preclaim_capacity"] = settings["preclaim_capacity"]
        result["preclaim_active_queue"] = settings.get("preclaim_active_queue", 0)
        result["refill"] = refill_result

    if outbox:
        result["outbox_jobs_received"] = len(backlog)
        if args.mode == "live":
            try:
                # v3 ACK archives successful delivery to publish.delivery_history and
                # deletes the live outbox row. Weekly metrics update history directly.
                result["outbox_sync"] = outbox.sync_scheduler_actions(result.get("actions", []))
            except SocialMarketOutboxError as exc:
                result["outbox_sync"] = {"error": str(exc)}
                print(json.dumps({"ok": False, "status": "outbox_ack_error", **result}, ensure_ascii=False, indent=2))
                return 3
        else:
            result["outbox_sync"] = {"dry_run": True, "mutations": 0}

    scheduled = sum(1 for action in result.get("actions", []) if action.get("type") == "scheduled")
    result["scheduled_this_run"] = scheduled
    result["weekly_target"] = int(settings.get("weekly_target", 300))
    print(json.dumps({"ok": True, "status": "completed", **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
