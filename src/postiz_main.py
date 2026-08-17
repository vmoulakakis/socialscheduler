from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from .postiz_client import PostizAPIError, PostizClient
from .socialmarket_outbox import SocialMarketOutboxClient, SocialMarketOutboxError

SERVICES = ("facebook", "instagram", "tiktok")


def _parse_dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def main() -> int:
    parser = argparse.ArgumentParser(description="SocialMarket outbox executor using Postiz as publisher")
    parser.add_argument("--mode", choices=["live", "dry-run"], default=os.getenv("SCHEDULER_MODE", "dry-run"))
    args = parser.parse_args()

    try:
        postiz = PostizClient.from_env()
        if not postiz.is_connected():
            raise PostizAPIError("Postiz API key is not connected")
        integrations = postiz.resolve_integrations()
        outbox = SocialMarketOutboxClient.from_env()
    except (PostizAPIError, SocialMarketOutboxError) as exc:
        print(json.dumps({"ok": False, "status": "configuration_error", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    capacity = {service: (10 if service in integrations else 0) for service in SERVICES}
    refill_result: dict[str, Any] = {}

    try:
        if args.mode == "dry-run":
            jobs = outbox.peek(30)
        else:
            refill_result = outbox.refill(int(os.getenv("OUTBOX_HORIZON_HOURS", "72")))
            jobs = outbox.claim_capacity(capacity)
    except SocialMarketOutboxError as exc:
        print(json.dumps({
            "ok": False,
            "status": "outbox_error",
            "publisher": "postiz",
            "integrations": integrations,
            "error": str(exc),
        }, ensure_ascii=False, indent=2))
        return 3

    if args.mode == "dry-run":
        print(json.dumps({
            "ok": True,
            "status": "dry_run",
            "publisher": "postiz",
            "integrations": integrations,
            "capacity": capacity,
            "jobs_preview": len(jobs),
            "jobs_by_platform": dict(Counter(str(job.get("platform") or "") for job in jobs)),
            "mutations": 0,
        }, ensure_ascii=False, indent=2))
        return 0

    actions: list[dict[str, Any]] = []
    failures = 0
    now = datetime.now(timezone.utc)

    for job in jobs:
        job_id = str(job.get("id") or "").strip()
        platform = str(job.get("platform") or "").strip().lower()
        integration_id = integrations.get(platform)
        scheduled_for = str(job.get("scheduled_for") or "").strip()

        if not job_id or not integration_id or not scheduled_for:
            failures += 1
            actions.append({"type": "blocked", "job_id": job_id, "platform": platform, "reason": "invalid_job_or_integration"})
            continue

        try:
            due_at = _parse_dt(scheduled_for)
        except Exception:
            outbox.ack(job_id, "failed", error="invalid_scheduled_for", metadata={"publisher": "postiz", "platform": platform})
            failures += 1
            actions.append({"type": "failed", "job_id": job_id, "platform": platform, "reason": "invalid_scheduled_for"})
            continue

        if due_at <= now:
            outbox.ack(job_id, "failed", error="scheduled_time_elapsed", metadata={"publisher": "postiz", "platform": platform})
            actions.append({"type": "skip_late", "job_id": job_id, "platform": platform, "due_at": scheduled_for})
            continue

        try:
            result = postiz.schedule_job(job, integration_id)
            post_id = str(result.get("postId") or "")
            outbox.ack(
                job_id,
                "scheduled",
                external_post_id=post_id,
                scheduled_at=scheduled_for,
                metadata={"publisher": "postiz", "platform": platform, "integration_id": integration_id},
            )
            actions.append({"type": "scheduled", "job_id": job_id, "platform": platform, "post_id": post_id, "due_at": scheduled_for})
        except PostizAPIError as exc:
            failures += 1
            # A deterministic malformed payload can be failed immediately. Auth, rate-limit,
            # network and server errors are intentionally left leased so the lease can expire
            # and a later run can retry without risking duplicate mutation retries.
            if exc.status_code == 400:
                try:
                    outbox.ack(job_id, "failed", error=str(exc), metadata={"publisher": "postiz", "platform": platform})
                except SocialMarketOutboxError:
                    pass
            actions.append({"type": "postiz_error", "job_id": job_id, "platform": platform, "error": str(exc)})

    scheduled = sum(1 for row in actions if row.get("type") == "scheduled")
    skipped = sum(1 for row in actions if row.get("type") == "skip_late")
    payload = {
        "ok": failures == 0,
        "status": "completed" if failures == 0 else "partial_failure",
        "publisher": "postiz",
        "integrations": integrations,
        "capacity": capacity,
        "refill": refill_result,
        "claimed": len(jobs),
        "claimed_by_platform": dict(Counter(str(job.get("platform") or "") for job in jobs)),
        "scheduled": scheduled,
        "skipped_late": skipped,
        "failures": failures,
        "actions": actions,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if failures == 0 else 4


if __name__ == "__main__":
    raise SystemExit(main())
