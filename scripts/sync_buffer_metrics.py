from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from src.buffer_client import BufferAPIError, BufferClient
from src.socialmarket_outbox import SocialMarketOutboxClient, SocialMarketOutboxError


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    organization_id = os.getenv("BUFFER_ORGANIZATION_ID", "").strip()
    if not organization_id:
        print(json.dumps({"ok": False, "error": "BUFFER_ORGANIZATION_ID is required"}, ensure_ascii=False))
        return 2

    try:
        buffer = BufferClient.from_env()
        outbox = SocialMarketOutboxClient.from_env()
        posts = buffer.sent_posts_with_metrics(organization_id, page_size=100, max_pages=5)

        # Provider truth drives lifecycle. A successful workflow or a scheduled ACK is
        # not publication proof. Read the durable scheduled delivery-history rows and
        # reconcile only when Buffer itself reports the matching post as sent.
        reconcile_candidates = outbox.provider_reconcile_candidates("buffer", limit=500)
        by_post_id = {
            str(row.get("external_post_id") or "").strip(): row
            for row in reconcile_candidates
            if str(row.get("external_post_id") or "").strip()
        }
        reconciled_published = 0
        reconcile_errors: list[dict[str, str]] = []

        rows = []
        for post in posts:
            post_id = str(post.get("id") or "").strip()
            if not post_id:
                continue
            metrics = post.get("metrics") if isinstance(post.get("metrics"), list) else []
            sent_at = post.get("sentAt")
            external_link = post.get("externalLink")

            candidate = by_post_id.get(post_id)
            if candidate and sent_at:
                try:
                    result = outbox.reconcile_provider_delivery({
                        "provider_key": "buffer",
                        "history_id": candidate.get("history_id"),
                        "status": "published",
                        "provider_status": "sent",
                        "external_post_id": post_id,
                        "published_at": sent_at,
                        "external_permalink": external_link,
                        "external_platform_post_id": post.get("externalId") or post.get("externalPostId"),
                    })
                    if result.get("status") == "published" or result.get("unchanged"):
                        reconciled_published += 1
                except SocialMarketOutboxError as exc:
                    reconcile_errors.append({"buffer_post_id": post_id, "error": str(exc)[:500]})

            rows.append({
                "buffer_post_id": post_id,
                "status": str(post.get("status") or ""),
                "sent_at": sent_at,
                "external_link": external_link,
                "metrics": metrics,
                "metrics_updated_at": post.get("metricsUpdatedAt") or _iso_now(),
            })

        result = outbox.metrics_batch(rows) if rows else {"updated": 0, "missing": 0}
        with_metrics = sum(1 for row in rows if row.get("metrics"))
        payload = {
            "ok": len(reconcile_errors) == 0,
            "buffer_sent_posts_scanned": len(rows),
            "provider_reconcile_candidates": len(reconcile_candidates),
            "provider_published_reconciled": reconciled_published,
            "provider_reconcile_errors": reconcile_errors,
            "posts_with_metrics": with_metrics,
            "database": result,
            "synced_at": _iso_now(),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if not reconcile_errors else 1
    except (BufferAPIError, SocialMarketOutboxError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc), "synced_at": _iso_now()}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
