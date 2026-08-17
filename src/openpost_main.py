from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from .openpost_client import OpenPostAPIError, OpenPostClient, SERVICES
from .socialmarket_outbox import SocialMarketOutboxClient, SocialMarketOutboxError


def _parse_dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def main() -> int:
    parser = argparse.ArgumentParser(description="SocialMarket outbox executor using OpenPost as publisher")
    parser.add_argument("--mode", choices=["live", "dry-run"], default=os.getenv("SCHEDULER_MODE", "dry-run"))
    args = parser.parse_args()

    try:
        openpost = OpenPostClient.from_env()
        accounts = openpost.account_ids_from_env()
        if not accounts:
            raise OpenPostAPIError(
                "At least one OPENPOST_ACCOUNT_FACEBOOK / OPENPOST_ACCOUNT_INSTAGRAM / OPENPOST_ACCOUNT_TIKTOK is required"
            )
        outbox = SocialMarketOutboxClient.from_env()
    except (OpenPostAPIError, SocialMarketOutboxError, ValueError) as exc:
        print(json.dumps({"ok": False, "status": "configuration_error", "publisher": "openpost", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    capacity = {service: (10 if service in accounts else 0) for service in SERVICES}
    refill_result: dict[str, Any] = {}

    try:
        if args.mode == "dry-run":
            jobs = outbox.peek(30)
        else:
            # Read OpenPost before leasing SocialMarket jobs. If auth/workspace is broken,
            # nothing is claimed and no approved job is stranded behind a lease.
            openpost.health()
            refill_result = outbox.refill(int(os.getenv("OUTBOX_HORIZON_HOURS", "72")))
            jobs = outbox.claim_capacity(capacity)
    except (OpenPostAPIError, SocialMarketOutboxError) as exc:
        print(json.dumps({
            "ok": False,
            "status": "publisher_or_outbox_error",
            "publisher": "openpost",
            "accounts": accounts,
            "capacity": capacity,
            "error": str(exc),
        }, ensure_ascii=False, indent=2))
        return 3

    if args.mode == "dry-run":
        print(json.dumps({
            "ok": True,
            "status": "dry_run",
            "publisher": "openpost",
            "workspace_id": openpost.workspace_id,
            "accounts": accounts,
            "capacity": capacity,
            "jobs_preview": len(jobs),
            "jobs_by_platform": dict(Counter(str(job.get("platform") or "") for job in jobs)),
            "unconfigured_platforms_in_preview": sorted({
                str(job.get("platform") or "").strip().lower()
                for job in jobs
                if str(job.get("platform") or "").strip().lower() not in accounts
            }),
            "mutations": 0,
        }, ensure_ascii=False, indent=2))
        return 0

    actions: list[dict[str, Any]] = []
    failures = 0
    now = datetime.now(timezone.utc)

    for job in jobs:
        job_id = str(job.get("id") or "").strip()
        platform = str(job.get("platform") or "").strip().lower()
        account_id = accounts.get(platform)
        scheduled_for = str(job.get("scheduled_for") or "").strip()

        if not job_id or not account_id or not scheduled_for:
            failures += 1
            actions.append({
                "type": "blocked",
                "job_id": job_id,
                "platform": platform,
                "reason": "invalid_job_or_openpost_account",
            })
            continue

        try:
            due_at = _parse_dt(scheduled_for)
        except Exception:
            try:
                outbox.ack(job_id, "failed", error="invalid_scheduled_for", metadata={"publisher": "openpost", "platform": platform})
            except SocialMarketOutboxError:
                pass
            failures += 1
            actions.append({"type": "failed", "job_id": job_id, "platform": platform, "reason": "invalid_scheduled_for"})
            continue

        if due_at <= now:
            try:
                outbox.ack(job_id, "failed", error="scheduled_time_elapsed", metadata={"publisher": "openpost", "platform": platform})
            except SocialMarketOutboxError:
                pass
            actions.append({"type": "skip_late", "job_id": job_id, "platform": platform, "due_at": scheduled_for})
            continue

        if platform in {"instagram", "tiktok"} and not str(job.get("media_url") or "").strip():
            try:
                outbox.ack(job_id, "failed", error="media_unavailable", metadata={"publisher": "openpost", "platform": platform})
            except SocialMarketOutboxError:
                pass
            failures += 1
            actions.append({"type": "blocked", "job_id": job_id, "platform": platform, "reason": "media_unavailable"})
            continue

        try:
            result = openpost.schedule_job(job, account_id)
            state = str(result.get("status") or "scheduled").strip().lower()
            publication_id = str(result.get("publicationId") or result.get("postId") or "")
            external_url = str(result.get("externalUrl") or "").strip() or None
            if state in {"published", "sent"}:
                outbox.ack(
                    job_id,
                    "published",
                    external_post_id=publication_id,
                    external_permalink=external_url,
                    published_at=datetime.now(timezone.utc).isoformat(),
                    metadata={
                        "publisher": "openpost",
                        "platform": platform,
                        "workspace_id": openpost.workspace_id,
                        "account_id": account_id,
                        "reconciled_existing": bool(result.get("reconciled")),
                    },
                )
                action_type = "already_published" if result.get("reconciled") else "published"
            else:
                outbox.ack(
                    job_id,
                    "scheduled",
                    external_post_id=publication_id,
                    external_permalink=external_url,
                    scheduled_at=str(result.get("scheduledAt") or scheduled_for),
                    metadata={
                        "publisher": "openpost",
                        "platform": platform,
                        "workspace_id": openpost.workspace_id,
                        "account_id": account_id,
                        "reconciled_existing": bool(result.get("reconciled")),
                    },
                )
                action_type = "already_scheduled" if result.get("reconciled") else "scheduled"
            actions.append({
                "type": action_type,
                "job_id": job_id,
                "platform": platform,
                "publication_id": publication_id,
                "due_at": str(result.get("scheduledAt") or scheduled_for),
                "external_url": external_url,
            })
        except OpenPostAPIError as exc:
            failures += 1
            # Only deterministic validation failures are terminal. Auth, conflict,
            # server and ambiguous network failures remain leased and can be safely
            # reconciled after lease expiry without issuing a blind duplicate write.
            if exc.status_code in {400, 422} and not exc.ambiguous:
                try:
                    outbox.ack(
                        job_id,
                        "failed",
                        error=str(exc),
                        metadata={"publisher": "openpost", "platform": platform, "deterministic": True},
                    )
                except SocialMarketOutboxError:
                    pass
            actions.append({
                "type": "openpost_error",
                "job_id": job_id,
                "platform": platform,
                "status_code": exc.status_code,
                "ambiguous": exc.ambiguous,
                "error": str(exc),
            })
        except SocialMarketOutboxError as exc:
            failures += 1
            actions.append({
                "type": "outbox_ack_error",
                "job_id": job_id,
                "platform": platform,
                "error": str(exc),
            })

    scheduled = sum(1 for row in actions if row.get("type") in {"scheduled", "already_scheduled"})
    published = sum(1 for row in actions if row.get("type") in {"published", "already_published"})
    skipped = sum(1 for row in actions if row.get("type") == "skip_late")
    payload = {
        "ok": failures == 0,
        "status": "completed" if failures == 0 else "partial_failure",
        "publisher": "openpost",
        "workspace_id": openpost.workspace_id,
        "accounts": accounts,
        "capacity": capacity,
        "refill": refill_result,
        "claimed": len(jobs),
        "claimed_by_platform": dict(Counter(str(job.get("platform") or "") for job in jobs)),
        "scheduled_or_reconciled": scheduled,
        "published_or_reconciled": published,
        "skipped_late": skipped,
        "failures": failures,
        "actions": actions,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if failures == 0 else 4


if __name__ == "__main__":
    raise SystemExit(main())
