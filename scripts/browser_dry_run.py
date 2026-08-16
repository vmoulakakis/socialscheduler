from __future__ import annotations

import argparse
import json

from src.direct_browser import CampaignDraft, run_campaign


def main() -> int:
    p = argparse.ArgumentParser(description="Prepare a social post in browser without final publish/schedule click")
    p.add_argument("platform", choices=["meta", "tiktok", "linkedin"])
    p.add_argument("--context-id", required=True)
    p.add_argument("--caption", required=True)
    p.add_argument("--media")
    p.add_argument("--tracking-url")
    p.add_argument("--scheduled-at")
    args = p.parse_args()

    draft = CampaignDraft(
        platform=args.platform,
        caption=args.caption,
        media_path=args.media,
        tracking_url=args.tracking_url,
        scheduled_at=args.scheduled_at,
    )
    result = run_campaign(draft, args.context_id, mode="dry-run", allow_live=False)
    print(json.dumps({
        "platform": result.platform,
        "mode": result.mode,
        "session_id": result.session_id,
        "live_view_url": result.live_view_url,
        "final_action_clicked": result.final_action_clicked,
        "screenshot_path": result.screenshot_path,
        "notes": result.notes,
    }, ensure_ascii=False, indent=2))
    if result.final_action_clicked:
        raise SystemExit("SAFETY VIOLATION: dry-run clicked a final action")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
