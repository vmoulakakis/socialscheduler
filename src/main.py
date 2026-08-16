from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .buffer_client import BufferAPIError, BufferClient, BufferRateLimitError
from .scheduler import ACTIVE_QUEUE_STATUSES, STATUS_READ_SET, load_json
from .scheduler_v2 import SocialScheduler
from .socialmarket_outbox import SocialMarketOutboxClient, SocialMarketOutboxError, jobs_to_backlog

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Safety-first Buffer social scheduler")
    parser.add_argument("--mode", choices=["live", "dry-run"], default=os.getenv("SCHEDULER_MODE", "dry-run"))
    parser.add_argument("--settings", default=str(ROOT / "config" / "settings.json"))
    parser.add_argument("--channels", default=str(ROOT / "config" / "channels.json"))
    parser.add_argument("--backlog", default=str(ROOT / "config" / "backlog.json"))
    args = parser.parse_args()

    settings = load_json(args.settings)
    env_org = os.getenv("BUFFER_ORGANIZATION_ID", "").strip()
    if env_org:
        settings["organization_id"] = env_org

    client = BufferClient.from_env()
    content_source = os.getenv("CONTENT_SOURCE", "socialmarket_outbox").strip() or "socialmarket_outbox"
    outbox: SocialMarketOutboxClient | None = None
    try:
        if content_source == "socialmarket_outbox":
            outbox = SocialMarketOutboxClient.from_env()
            requested_limit = int(settings.get("max_creates_per_run", settings.get("queue_limit", 10)))
            if args.mode == "dry-run":
                jobs = outbox.peek(requested_limit)
            else:
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

                active_queue = sum(1 for post in current_posts if post.get("status") in ACTIVE_QUEUE_STATUSES)
                free_slots = max(0, int(settings.get("queue_limit", 10)) - active_queue)
                claim_limit = min(requested_limit, free_slots)
                jobs = outbox.claim(claim_limit) if claim_limit > 0 else []
                settings["preclaim_active_queue"] = active_queue
                settings["preclaim_free_slots"] = free_slots
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

    scheduler = SocialScheduler(client=client,settings=settings,channels=load_json(args.channels),backlog=backlog,mode=args.mode)
    try:
        result = scheduler.run()
    except BufferRateLimitError as exc:
        print(json.dumps({"ok": True,"status": "rate_limited","retry_after_seconds": exc.retry_after_seconds,"action": "defer_without_writes"}, ensure_ascii=False, indent=2))
        return 0
    except BufferAPIError as exc:
        print(json.dumps({"ok": False, "status": "error", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    if "preclaim_active_queue" in settings:
        result["preclaim_active_queue"] = settings["preclaim_active_queue"]
        result["preclaim_free_slots"] = settings["preclaim_free_slots"]

    buffer_posts = result.pop("buffer_posts", [])
    if outbox:
        result["outbox_jobs_received"] = len(backlog)
        if args.mode == "live":
            try:
                action_sync = outbox.sync_scheduler_actions(result.get("actions", []))
                tracked = outbox.reconcile_jobs()
                status_sync = outbox.sync_buffer_statuses(tracked, buffer_posts)
                result["outbox_sync"] = {"actions": action_sync, "buffer": status_sync, "tracked": len(tracked)}
            except SocialMarketOutboxError as exc:
                result["outbox_sync"] = {"error": str(exc)}
                print(json.dumps({"ok": False, "status": "outbox_ack_error", **result}, ensure_ascii=False, indent=2))
                return 3
        else:
            result["outbox_sync"] = {"dry_run": True, "mutations": 0}

    print(json.dumps({"ok": True, "status": "completed", **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
