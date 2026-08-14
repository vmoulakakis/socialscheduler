from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .buffer_client import BufferAPIError, BufferClient, BufferRateLimitError
from .scheduler import load_json
from .scheduler_v2 import SocialScheduler

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Safety-first Buffer social scheduler")
    parser.add_argument("--mode", choices=["live", "dry-run"], default=os.getenv("SCHEDULER_MODE", "live"))
    parser.add_argument("--settings", default=str(ROOT / "config" / "settings.json"))
    parser.add_argument("--channels", default=str(ROOT / "config" / "channels.json"))
    parser.add_argument("--backlog", default=str(ROOT / "config" / "backlog.json"))
    args = parser.parse_args()

    settings = load_json(args.settings)
    env_org = os.getenv("BUFFER_ORGANIZATION_ID", "").strip()
    if env_org:
        settings["organization_id"] = env_org
    if os.getenv("ASSET_REPOSITORY"):
        settings["asset_repo"] = os.environ["ASSET_REPOSITORY"]
    if os.getenv("ASSET_REF"):
        settings["asset_ref"] = os.environ["ASSET_REF"]

    client = BufferClient.from_env()
    scheduler = SocialScheduler(
        client=client,
        settings=settings,
        channels=load_json(args.channels),
        backlog=load_json(args.backlog),
        mode=args.mode,
    )
    try:
        result = scheduler.run()
    except BufferRateLimitError as exc:
        print(json.dumps({
            "ok": True,
            "status": "rate_limited",
            "retry_after_seconds": exc.retry_after_seconds,
            "action": "defer_without_writes",
        }, ensure_ascii=False, indent=2))
        return 0
    except BufferAPIError as exc:
        print(json.dumps({"ok": False, "status": "error", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps({"ok": True, "status": "completed", **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
