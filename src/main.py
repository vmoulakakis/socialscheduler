from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path

from .buffer_client import BufferAPIError, BufferClient, BufferRateLimitError
from .scheduler import ACTIVE_QUEUE_STATUSES, STATUS_READ_SET, load_json
from .scheduler_v2 import SocialScheduler
from .socialmarket_outbox import SocialMarketOutboxClient, SocialMarketOutboxError, jobs_to_backlog

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ("facebook", "instagram", "tiktok")


def main() -> int:
    parser = argparse.ArgumentParser(description="Safety-first Buffer social scheduler")
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
    try:
        if content_source == "socialmarket_outbox":
            outbox = SocialMarketOutboxClient.from_env()
            per_channel_limit = int(settings.get("queue_limit_per_channel", settings.get("queue_limit", 10)))
            try:
                current_posts = client.posts(settings["organization_id"], STATUS_READ_SET)
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

            active_by_service: dict[str, int] = {}
            capacity: dict[str, int] = {}
            for service in SERVICES:
                channel_id = (channels.get(service) or {}).get("id")
                active = sum(
                    1 for post in current_posts
                    if post.get("status") in ACTIVE_QUEUE_STATUSES and post.get("channelId") == channel_id
                ) if channel_id else 0
                active_by_service[service] = active
                capacity[service] = max(0, per_channel_limit - active) if channel_id else 0

            health = outbox.health()
            settings["outbox_health_ok"] = bool(health.get("ok", True))
            settings["preclaim_active_by_service"] = active_by_service
            settings["preclaim_capacity_by_service"] = capacity
            settings["preclaim_active_queue"] = sum(active_by_service.values())
            settings["preclaim_free_slots"] = sum(capacity.values())

            if args.mode == "dry-run":
                jobs = outbox.peek(max(1, min(50, sum(capacity.values()) or per_channel_limit * len(SERVICES))))
                settings["outbox_refill"] = {"dry_run": True, "mutations": 0}
            else:
                settings["outbox_refill"] = outbox.refill(int(settings.get("rolling_refill_hours", 72)))
                jobs = outbox.claim_capacity(capacity) if any(capacity.values()) else []

            backlog = jobs_to_backlog(jobs)
            settings["content_source"] = "socialmarket_outbox"
        elif content_source == "legacy_backlog":
            backlog = load_json(args.backlog)
            settings["content_source"] = "legacy_backlog"
        else:
            raise SocialMarketOutboxError(f"Unsupported CONTENT_SOURCE={content_source}")
    except SocialMarketOutboxError as exc:
        print(json.dumps({"ok": False, "status": "outbox_error", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 3

    scheduler = SocialScheduler(client=client, settings=settings, channels=channels, backlog=backlog, mode=args.mode)
    try:
        result = scheduler.run()
    except BufferRateLimitError as exc:
        print(json.dumps({"ok": True, "status": "rate_limited", "retry_after_seconds": exc.retry_after_seconds, "action": "defer_without_writes"}, ensure_ascii=False, indent=2))
        return 0
    except BufferAPIError as exc:
        print(json.dumps({"ok": False, "status": "error", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    for key in (
        "preclaim_active_queue", "preclaim_free_slots", "preclaim_active_by_service",
        "preclaim_capacity_by_service", "outbox_health_ok", "outbox_refill",
    ):
        if key in settings:
            result[key] = settings[key]

    buffer_posts = result.pop("buffer_posts", [])
    if outbox:
        result["outbox_jobs_received"] = len(backlog)
        result["outbox_jobs_received_by_platform"] = dict(Counter(item.get("platform") for item in jobs))
        if args.mode == "live":
            try:
                action_sync = outbox.sync_scheduler_actions(result.get("actions", []))
                tracked = outbox.reconcile_jobs()
                status_sync = outbox.sync_buffer_statuses(tracked, buffer_posts)
                pending = outbox.peek(50)
                result["outbox_pending_preview_count"] = len(pending)
                result["outbox_pending_by_platform"] = dict(Counter(job.get("platform") for job in pending))
                result["outbox_sync"] = {"actions": action_sync, "buffer": status_sync, "tracked": len(tracked)}
            except SocialMarketOutboxError as exc:
                result["outbox_sync"] = {"error": str(exc)}
                print(json.dumps({"ok": False, "status": "outbox_ack_error", **result}, ensure_ascii=False, indent=2))
                return 3
        else:
            result["outbox_pending_preview_count"] = len(jobs)
            result["outbox_pending_by_platform"] = dict(Counter(item.get("platform") for item in jobs))
            result["outbox_sync"] = {"dry_run": True, "mutations": 0}

    print(json.dumps({"ok": True, "status": "completed", **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
