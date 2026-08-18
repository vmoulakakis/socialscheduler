from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from .postzen_client import PostZenAPIError, PostZenClient
from .socialmarket_outbox import SocialMarketOutboxClient, SocialMarketOutboxError


def _parse_dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _routes_from_env() -> list[str]:
    raw = os.getenv("POSTZEN_PLATFORMS", "linkedin,instagram,facebook")
    routes: list[str] = []
    for item in raw.split(","):
        route = item.strip().lower()
        if route and route != "tiktok" and route not in routes:
            routes.append(route)
    return routes


def main() -> int:
    parser = argparse.ArgumentParser(description="Provider-aware SocialScheduler executor using PostZen")
    parser.add_argument("--mode", choices=["live", "dry-run"], default=os.getenv("SCHEDULER_MODE", "dry-run"))
    args = parser.parse_args()

    try:
        postzen = PostZenClient.from_env()
        connected = postzen.connected_platforms()
        requested = _routes_from_env()
        routes = [p for p in requested if p in connected and p in {"facebook", "instagram", "linkedin"}]
        outbox = SocialMarketOutboxClient.from_env()
    except (PostZenAPIError, SocialMarketOutboxError) as exc:
        print(json.dumps({"ok": False, "status": "configuration_error", "publisher": "postzen", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    if not routes:
        print(json.dumps({
            "ok": True,
            "status": "no_execution_routes",
            "publisher": "postzen",
            "connected_platforms": sorted(connected),
            "requested_platforms": requested,
            "reason": "No connected PostZen account matches an orchestrated supported route",
        }, ensure_ascii=False, indent=2))
        return 0

    if args.mode == "dry-run":
        try:
            preview = outbox.peek(50)
        except SocialMarketOutboxError as exc:
            print(json.dumps({"ok": False, "status": "outbox_error", "publisher": "postzen", "error": str(exc)}, ensure_ascii=False, indent=2))
            return 3
        rows = [j for j in preview if str(j.get("platform") or "").lower() in routes]
        print(json.dumps({
            "ok": True,
            "status": "dry_run",
            "publisher": "postzen",
            "routes": routes,
            "connected_platforms": sorted(connected),
            "candidate_jobs": len(rows),
            "candidate_by_platform": dict(Counter(str(j.get("platform") or "") for j in rows)),
            "mutations": 0,
        }, ensure_ascii=False, indent=2))
        return 0

    capacity = {name: (10 if name in routes else 0) for name in ("facebook", "instagram", "tiktok", "linkedin")}
    try:
        refill_result = outbox.refill(int(os.getenv("OUTBOX_HORIZON_HOURS", "72")))
        jobs = outbox.claim_provider_capacity("postzen", capacity, executor="socialscheduler-postzen")
    except SocialMarketOutboxError as exc:
        print(json.dumps({"ok": False, "status": "outbox_error", "publisher": "postzen", "routes": routes, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 3

    actions: list[dict[str, Any]] = []
    failures = 0
    now = datetime.now(timezone.utc)

    for job in jobs:
        job_id = str(job.get("id") or "").strip()
        platform = str(job.get("platform") or "").strip().lower()
        scheduled_for = str(job.get("scheduled_for") or "").strip()
        if not job_id or platform not in routes or not scheduled_for:
            failures += 1
            actions.append({"type": "blocked", "job_id": job_id, "platform": platform, "reason": "invalid_job_or_route"})
            continue
        try:
            due_at = _parse_dt(scheduled_for)
        except Exception:
            outbox.ack(job_id, "failed", error="invalid_scheduled_for", metadata={"publisher": "postzen", "platform": platform})
            failures += 1
            actions.append({"type": "failed", "job_id": job_id, "platform": platform, "reason": "invalid_scheduled_for"})
            continue
        if due_at <= now:
            outbox.ack(job_id, "failed", error="scheduled_time_elapsed", metadata={"publisher": "postzen", "platform": platform})
            actions.append({"type": "skip_late", "job_id": job_id, "platform": platform, "due_at": scheduled_for})
            continue
        try:
            result = postzen.schedule_job(job)
            post_id = postzen.extract_post_id(result)
            permalink = postzen.extract_permalink(result)
            outbox.ack(
                job_id,
                "scheduled",
                external_post_id=post_id or None,
                external_permalink=permalink or None,
                scheduled_at=scheduled_for,
                metadata={"publisher": "postzen", "platform": platform, "provider_response_id": post_id or None},
            )
            actions.append({"type": "scheduled", "job_id": job_id, "platform": platform, "post_id": post_id, "due_at": scheduled_for})
        except PostZenAPIError as exc:
            failures += 1
            if exc.status_code in {400, 401, 403, 404, 422}:
                try:
                    outbox.ack(job_id, "failed", error=str(exc), metadata={"publisher": "postzen", "platform": platform})
                except SocialMarketOutboxError:
                    pass
            actions.append({"type": "postzen_error", "job_id": job_id, "platform": platform, "status_code": exc.status_code, "error": str(exc)})

    scheduled = sum(1 for x in actions if x.get("type") == "scheduled")
    payload = {
        "ok": failures == 0,
        "status": "completed" if failures == 0 else "partial_failure",
        "publisher": "postzen",
        "routes": routes,
        "connected_platforms": sorted(connected),
        "refill": refill_result,
        "claimed": len(jobs),
        "claimed_by_platform": dict(Counter(str(j.get("platform") or "") for j in jobs)),
        "scheduled": scheduled,
        "failures": failures,
        "actions": actions,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if failures == 0 else 4


if __name__ == "__main__":
    raise SystemExit(main())
