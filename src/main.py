from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .buffer_client import BufferAPIError, BufferClient, BufferRateLimitError
from .scheduler import load_json
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

    content_source = os.getenv("CONTENT_SOURCE", "socialmarket_outbox").strip() or "socialmarket_outbox"
    outbox: SocialMarketOutboxClient | None = None
    try:
        if content_source == "socialmarket_outbox":
            outbox = SocialMarketOutboxClient.from_env()
            limit = int(settings.get("max_creates_per_run", settings.get("queue_limit", 10)))
            jobs = outbox.peek(limit) if args.mode == "dry-run" else outbox.claim(limit)
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

    client = BufferClient.from_env()
    scheduler = SocialScheduler(client=client,settings=settings,channels=load_json(args.channels),backlog=backlog,mode=args.mode)
    try:
        result = scheduler.run()
    except BufferRateLimitError as exc:
        print(json.dumps({"ok": True,"status": "rate_limited","retry_after_seconds": exc.retry_after_seconds,"action": "defer_without_writes"}, ensure_ascii=False, indent=2))
        return 0
    except BufferAPIError as exc:
        print(json.dumps({"ok": False, "status": "error", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2

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
