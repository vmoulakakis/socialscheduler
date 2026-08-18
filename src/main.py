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


def snapshot_queue_truth(snapshot: dict, channels: dict, per_channel_limit: int) -> tuple[dict, dict]:
    active_by_channel = Counter(
        str(post.get("channelId") or "")
        for post in snapshot.get("posts", [])
        if post.get("status") in ACTIVE_QUEUE_STATUSES
    )
    channel_slo: dict[str, dict] = {}
    for service in SERVICES:
        channel_id = str((channels.get(service) or {}).get("id") or "")
        active = int(active_by_channel.get(channel_id, 0))
        missing = max(0, per_channel_limit - active)
        channel_slo[service] = {
            "active": active,
            "limit": per_channel_limit,
            "missing": missing,
            "fill_rate_pct": round((active / per_channel_limit) * 100, 2) if per_channel_limit else 0.0,
            "met": missing == 0,
        }
    total_active = sum(row["active"] for row in channel_slo.values())
    total_limit = per_channel_limit * len(SERVICES)
    total_missing = max(0, total_limit - total_active)
    queue_slo = {
        "active": total_active,
        "limit": total_limit,
        "missing": total_missing,
        "fill_rate_pct": round((total_active / total_limit) * 100, 2) if total_limit else 0.0,
        "met": total_missing == 0,
    }
    return queue_slo, channel_slo


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
    per_channel_limit = int(settings.get("queue_limit_per_channel", settings.get("queue_limit", 10)))

    try:
        if content_source == "socialmarket_outbox":
            outbox = SocialMarketOutboxClient.from_env()
            settings["content_source"] = "socialmarket_outbox"
            if args.mode == "live":
                try:
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
                queue_slo, channel_slo = snapshot_queue_truth(snapshot, channels, per_channel_limit)
                for service in SERVICES:
                    capacity[service] = int(channel_slo[service]["missing"])

                refill_result = outbox.refill(int(settings.get("outbox_horizon_hours", 72)))
                jobs = outbox.claim_provider_capacity(
                    "buffer",
                    capacity,
                    executor="socialscheduler-buffer",
                )
                settings["preclaim_capacity"] = capacity
                settings["preclaim_active_queue"] = int(queue_slo["active"])
            else:
                jobs = outbox.peek(int(settings.get("max_creates_per_run", 30)))
            backlog = jobs_to_backlog(jobs)
        elif content_source == "legacy_backlog":
            backlog = load_json(args.backlog)
            settings["content_source"] = "legacy_backlog"
        else:
            raise SocialMarketOutboxError(f"Unsupported CONTENT_SOURCE={content_source}")
    except (SocialMarketOutboxError, BufferAPIError) as exc:
        payload: dict = {"ok": False, "status": "outbox_error", "error": str(exc)}
        if snapshot is not None and not snapshot.get("has_next_page"):
            queue_slo, channel_slo = snapshot_queue_truth(snapshot, channels, per_channel_limit)
            payload.update({
                "queue_slo": queue_slo,
                "channel_queue_slo": channel_slo,
                "full_truth_source": "buffer_runtime_snapshot_before_outbox_failure",
                "preclaim_capacity": {service: int(channel_slo[service]["missing"]) for service in SERVICES},
                "preclaim_active_queue": int(queue_slo["active"]),
                "refill": refill_result,
            })
        print(json.dumps(payload, ensure_ascii=False, indent=2))
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
        result["outbox_jobs_received_by_platform"] = dict(Counter(job.get("platform") for job in jobs))
        if args.mode == "live":
            try:
                result["outbox_sync"] = outbox.sync_scheduler_actions(result.get("actions", []), publisher="buffer")
                pending = outbox.peek(50)
                result["outbox_pending_preview_count"] = len(pending)
                result["outbox_pending_by_platform"] = dict(Counter(job.get("platform") for job in pending))
            except SocialMarketOutboxError as exc:
                result["outbox_sync"] = {"error": str(exc)}
                print(json.dumps({"ok": False, "status": "outbox_ack_error", **result}, ensure_ascii=False, indent=2))
                return 3
        else:
            result["outbox_pending_preview_count"] = len(jobs)
            result["outbox_pending_by_platform"] = dict(Counter(job.get("platform") for job in jobs))
            result["outbox_sync"] = {"dry_run": True, "mutations": 0}

    scheduled = sum(1 for action in result.get("actions", []) if action.get("type") == "scheduled")
    result["scheduled_this_run"] = scheduled
    result["weekly_target"] = int(settings.get("weekly_target", 300))
    print(json.dumps({"ok": True, "status": "completed", **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
