from __future__ import annotations

import argparse
import json
from typing import Any

from src.brightbean_client import BrightBeanAPIError, BrightBeanClient
from src.postzen_client import PostZenAPIError, PostZenClient
from src.socialmarket_outbox import SocialMarketOutboxClient, SocialMarketOutboxError


PUBLISHED = {"published", "sent"}
FAILED = {"failed", "error"}


def _first_mapping(*values: Any) -> dict[str, Any]:
    return next((value for value in values if isinstance(value, dict)), {})


def normalize_provider_post(provider: str, payload: dict[str, Any], platform: str) -> dict[str, Any]:
    root = _first_mapping(payload.get("post"), payload.get("data"), payload)
    children = root.get("platform_posts") or root.get("platforms") or []
    child: dict[str, Any] = {}
    if isinstance(children, list):
        wanted = {platform.lower(), f"{platform.lower()}_personal", f"{platform.lower()}_company"}
        for value in children:
            if not isinstance(value, dict):
                continue
            if not child:
                child = value
            if str(value.get("platform") or "").lower() in wanted:
                child = value
                break

    status = str(child.get("status") or root.get("status") or root.get("state") or "").strip().lower()
    published_at = str(
        child.get("published_at") or child.get("publishedAt")
        or root.get("published_at") or root.get("publishedAt") or ""
    ).strip()
    platform_post_id = str(
        child.get("platform_post_id") or child.get("platformPostId")
        or root.get("platform_post_id") or root.get("platformPostId") or ""
    ).strip()
    permalink = str(
        child.get("platformPostUrl") or child.get("permalink") or child.get("url")
        or root.get("platformPostUrl") or root.get("permalink") or root.get("url") or ""
    ).strip()
    error = str(
        child.get("publish_error") or child.get("error")
        or root.get("publish_error") or root.get("error") or ""
    ).strip()

    # Missing timestamps remain UNKNOWN; reconciliation time is never used as
    # a substitute for the provider's actual publication timestamp.
    if status in PUBLISHED and published_at:
        return {
            "terminal": True, "status": "published", "provider_status": status,
            "published_at": published_at, "external_platform_post_id": platform_post_id,
            "external_permalink": permalink,
        }
    if status in FAILED:
        return {
            "terminal": True, "status": "failed", "provider_status": status,
            "error": error or f"{provider}_provider_reported_{status}",
        }
    return {"terminal": False, "provider_status": status or "unknown"}


def reconcile(provider: str, limit: int) -> dict[str, Any]:
    outbox = SocialMarketOutboxClient.from_env()
    client: Any = BrightBeanClient.from_env() if provider == "brightbean" else PostZenClient.from_env()
    candidates = outbox.provider_reconcile_candidates(provider, limit)
    counts = {"candidates": len(candidates), "published": 0, "failed": 0, "unchanged": 0, "unavailable": 0}
    samples: list[dict[str, Any]] = []

    for row in candidates:
        external_id = str(row.get("external_post_id") or "").strip()
        try:
            observed = normalize_provider_post(provider, client.get_post(external_id), str(row.get("platform") or ""))
        except (BrightBeanAPIError, PostZenAPIError) as exc:
            counts["unavailable"] += 1
            if len(samples) < 8:
                samples.append({"history_id": row.get("history_id"), "result": "unavailable", "error": str(exc)[:240]})
            continue
        if not observed.get("terminal"):
            counts["unchanged"] += 1
            continue
        result = outbox.reconcile_provider_delivery({
            "history_id": row.get("history_id"),
            "provider_key": provider,
            "external_post_id": external_id,
            **{key: value for key, value in observed.items() if key != "terminal"},
        })
        terminal_status = str(result.get("status") or observed.get("status"))
        counts[terminal_status] = counts.get(terminal_status, 0) + 1

    return {"provider": provider, **counts, "samples": samples, "policy": "verified-provider-readback-v11"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile acknowledged provider schedules against provider truth")
    parser.add_argument("--provider", required=True, choices=("postzen", "brightbean"))
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    try:
        result = reconcile(args.provider, args.limit)
    except SocialMarketOutboxError as exc:
        # Rolling-deployment compatibility: an older gateway may not expose
        # the v11 readback action yet. Report UNKNOWN without blocking writes.
        result = {"provider": args.provider, "reconciliation": "unavailable", "error": str(exc)[:500]}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
