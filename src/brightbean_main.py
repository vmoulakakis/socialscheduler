from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from .brightbean_client import BrightBeanAPIError, BrightBeanClient
from .socialmarket_outbox import SocialMarketOutboxClient, SocialMarketOutboxError


def _parse_dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _routes_from_env() -> list[str]:
    raw = os.getenv("BRIGHTBEAN_PLATFORMS", "linkedin,facebook,instagram,tiktok")
    routes: list[str] = []
    for item in raw.split(","):
        route = item.strip().lower()
        if route in {"facebook", "instagram", "tiktok", "linkedin"} and route not in routes:
            routes.append(route)
    return routes


def _discover_accounts(client: BrightBeanClient, requested: list[str]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    connected = [
        a for a in client.list_accounts()
        if str(a.get("connection_status") or "").lower() == "connected"
    ]
    resolved: dict[str, dict[str, Any]] = {}
    unavailable: dict[str, str] = {}
    for route in requested:
        configured_id = os.getenv(f"BRIGHTBEAN_ACCOUNT_{route.upper()}", "").strip()
        if route == "linkedin":
            candidates = [a for a in connected if str(a.get("platform") or "").lower() in {"linkedin_personal", "linkedin_company", "linkedin"}]
        else:
            candidates = [a for a in connected if str(a.get("platform") or "").lower() == route]
        if configured_id:
            matches = [a for a in candidates if str(a.get("id") or "") == configured_id]
            if matches:
                resolved[route] = matches[0]
            else:
                unavailable[route] = "configured account id is not connected"
        elif len(candidates) == 1:
            resolved[route] = candidates[0]
        elif not candidates:
            unavailable[route] = "no connected account"
        else:
            unavailable[route] = "multiple accounts; explicit account id required"
    return resolved, unavailable


def main() -> int:
    parser = argparse.ArgumentParser(description="Provider-aware SocialScheduler executor using BrightBean")
    parser.add_argument("--mode", choices=["live", "dry-run"], default=os.getenv("SCHEDULER_MODE", "dry-run"))
    args = parser.parse_args()

    requested = _routes_from_env()
    try:
        brightbean = BrightBeanClient.from_env()
        me = brightbean.me()
        accounts, unavailable = _discover_accounts(brightbean, requested)
        routes = list(accounts)
        outbox = SocialMarketOutboxClient.from_env()
    except (BrightBeanAPIError, SocialMarketOutboxError) as exc:
        print(json.dumps({
            "ok": False,
            "status": "configuration_error",
            "publisher": "brightbean",
            "requested_routes": requested,
            "error": str(exc),
        }, ensure_ascii=False, indent=2))
        return 2

    account_summary = {
        route: {
            "id": str(account.get("id") or ""),
            "platform": account.get("platform"),
            "name": account.get("account_name") or account.get("name"),
            "handle": account.get("account_handle") or account.get("handle"),
        }
        for route, account in accounts.items()
    }

    if not routes:
        print(json.dumps({
            "ok": True,
            "status": "no_execution_routes",
            "publisher": "brightbean",
            "workspace": me.get("workspace_name"),
            "requested_routes": requested,
            "unavailable": unavailable,
            "reason": "BrightBean is connected but no unambiguous connected social account is currently executable",
        }, ensure_ascii=False, indent=2))
        return 0

    if args.mode == "dry-run":
        try:
            preview = outbox.peek(50)
        except SocialMarketOutboxError as exc:
            print(json.dumps({"ok": False, "status": "outbox_error", "publisher": "brightbean", "error": str(exc)}, ensure_ascii=False, indent=2))
            return 3
        jobs = [job for job in preview if str(job.get("platform") or "").strip().lower() in routes]
        print(json.dumps({
            "ok": True,
            "status": "dry_run",
            "publisher": "brightbean",
            "workspace": me.get("workspace_name"),
            "permissions": me.get("permissions"),
            "routes": routes,
            "unavailable": unavailable,
            "accounts": account_summary,
            "jobs_preview": len(jobs),
            "jobs_by_platform": dict(Counter(str(job.get("platform") or "") for job in jobs)),
            "mutations": 0,
        }, ensure_ascii=False, indent=2))
        return 0

    capacity = {name: (10 if name in routes else 0) for name in ("facebook", "instagram", "tiktok", "linkedin")}
    try:
        refill_result = outbox.refill(int(os.getenv("OUTBOX_HORIZON_HOURS", "72")))
        jobs = outbox.claim_provider_capacity(
            "brightbean",
            capacity,
            executor="socialscheduler-brightbean",
        )
    except SocialMarketOutboxError as exc:
        print(json.dumps({
            "ok": False,
            "status": "outbox_error",
            "publisher": "brightbean",
            "routes": routes,
            "accounts": account_summary,
            "error": str(exc),
        }, ensure_ascii=False, indent=2))
        return 3

    actions: list[dict[str, Any]] = []
    failures = 0
    now = datetime.now(timezone.utc)

    for job in jobs:
        job_id = str(job.get("id") or "").strip()
        platform = str(job.get("platform") or "").strip().lower()
        scheduled_for = str(job.get("scheduled_for") or "").strip()
        account = accounts.get(platform)

        if not job_id or not scheduled_for or account is None:
            failures += 1
            actions.append({"type": "blocked", "job_id": job_id, "platform": platform, "reason": "invalid_job_or_route"})
            continue

        try:
            due_at = _parse_dt(scheduled_for)
        except Exception:
            outbox.ack(job_id, "failed", error="invalid_scheduled_for", metadata={"publisher": "brightbean", "platform": platform})
            failures += 1
            actions.append({"type": "failed", "job_id": job_id, "platform": platform, "reason": "invalid_scheduled_for"})
            continue

        if due_at <= now:
            outbox.ack(job_id, "failed", error="scheduled_time_elapsed", metadata={"publisher": "brightbean", "platform": platform})
            actions.append({"type": "skip_late", "job_id": job_id, "platform": platform, "due_at": scheduled_for})
            continue

        try:
            result = brightbean.schedule_job(job, account)
            post_id = str(result.get("id") or "").strip()
            permalink = str(result.get("external_permalink") or result.get("permalink") or "").strip()
            outbox.ack(
                job_id,
                "scheduled",
                external_post_id=post_id or None,
                external_permalink=permalink or None,
                scheduled_at=scheduled_for,
                metadata={
                    "publisher": "brightbean",
                    "platform": platform,
                    "brightbean_account_id": str(account.get("id") or ""),
                    "brightbean_platform": account.get("platform"),
                },
            )
            actions.append({
                "type": "scheduled",
                "job_id": job_id,
                "platform": platform,
                "post_id": post_id,
                "due_at": scheduled_for,
            })
        except BrightBeanAPIError as exc:
            failures += 1
            if exc.status_code in {400, 401, 403, 404, 422}:
                try:
                    outbox.ack(
                        job_id,
                        "failed",
                        error=str(exc),
                        metadata={"publisher": "brightbean", "platform": platform},
                    )
                except SocialMarketOutboxError:
                    pass
            actions.append({
                "type": "brightbean_error",
                "job_id": job_id,
                "platform": platform,
                "status_code": exc.status_code,
                "error": str(exc),
            })

    scheduled = sum(1 for row in actions if row.get("type") == "scheduled")
    payload = {
        "ok": failures == 0,
        "status": "completed" if failures == 0 else "partial_failure",
        "publisher": "brightbean",
        "routes": routes,
        "unavailable": unavailable,
        "accounts": account_summary,
        "refill": refill_result,
        "claimed": len(jobs),
        "claimed_by_platform": dict(Counter(str(job.get("platform") or "") for job in jobs)),
        "scheduled": scheduled,
        "failures": failures,
        "actions": actions,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if failures == 0 else 4


if __name__ == "__main__":
    raise SystemExit(main())
