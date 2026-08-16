from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from src.buffer_client import BufferClient

ATHENS = ZoneInfo("Europe/Athens")
ORG_ID = os.getenv("BUFFER_ORGANIZATION_ID", "68a86463018d512de98d6315").strip()
OUT = Path(os.getenv("RECONCILE_EXPORT_PATH", "artifacts/buffer-target-reconciliation.json"))
TARGETS = {
    "6a810d9bb989c1db86eb324d": {"platform": "facebook", "expected_due_at": "2026-08-18T15:30:00+00:00", "source_key": "ps-20260818-watering-planter"},
    "6a810d9bced1ab157dc54dc2": {"platform": "instagram", "expected_due_at": "2026-08-18T16:15:00+00:00", "source_key": "ps-20260818-watering-planter"},
    "6a810d9c13afe87ec8a93fb2": {"platform": "tiktok", "expected_due_at": "2026-08-18T17:15:00+00:00", "source_key": "ps-20260818-watering-planter"},
}


def main() -> int:
    client = BufferClient.from_env()
    snapshot = client.runtime_snapshot(ORG_ID)
    operational = client.posts(ORG_ID, ["scheduled", "sending", "sent", "error"])

    by_id = {str(post.get("id") or ""): post for post in operational if post.get("id")}
    active_ids = {str(post.get("id") or "") for post in snapshot.get("posts", []) if post.get("id")}
    now = datetime.now(timezone.utc)
    rows = []

    for post_id, expected in TARGETS.items():
        post = by_id.get(post_id)
        expected_due = datetime.fromisoformat(expected["expected_due_at"].replace("Z", "+00:00"))
        if post:
            classification = str(post.get("status") or "present_unknown_status")
            evidence = "buffer_posts_operational_index"
        elif post_id in active_ids:
            classification = "active_unindexed"
            evidence = "buffer_runtime_snapshot"
        elif expected_due > now:
            classification = "absent_before_expected_publish"
            evidence = "absent_from_current_active_and_scheduled/sending/sent/error_indexes"
        else:
            classification = "absent_after_expected_publish"
            evidence = "absent_from_current_active_and_scheduled/sending/sent/error_indexes"

        rows.append({
            "buffer_post_id": post_id,
            **expected,
            "classification": classification,
            "evidence": evidence,
            "buffer_post": post,
        })

    payload = {
        "ok": True,
        "generated_at": datetime.now(ATHENS).isoformat(timespec="seconds"),
        "organization_id": ORG_ID,
        "current_active_queue": len(snapshot.get("posts", [])),
        "operational_posts_scanned": len(operational),
        "targets": rows,
        "truth_note": "A future-due target absent from both the live active queue and Buffer scheduled/sending/sent/error indexes is no longer scheduled in Buffer. This script is read-only and performs no mutations.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
