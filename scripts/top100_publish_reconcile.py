#!/usr/bin/env python3
"""Build an idempotent publication reconciliation payload from scheduler truth.

This helper is intentionally narrow: it never creates posts. It consumes scheduler/provider
truth artifacts and emits records that SocialMarket can use to retire provider-confirmed
published products from the active Top-100. Safe to run after partial failures.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def walk(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def first(d: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = d.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def normalize_platform(value: Any) -> str | None:
    if not value:
        return None
    s = str(value).strip().lower()
    aliases = {"fb": "facebook", "ig": "instagram", "tt": "tiktok", "tik_tok": "tiktok"}
    return aliases.get(s, s)


def extract(paths: list[Path]) -> list[dict[str, Any]]:
    rows: dict[tuple[str, str, str], dict[str, Any]] = {}
    for path in paths:
        data = load_json(path)
        if data is None:
            continue
        for node in walk(data):
            source_hash = first(node, "source_hash", "content_hash", "intent_hash")
            provider_post_id = first(node, "provider_post_id", "buffer_post_id", "post_id", "provider_id")
            platform = normalize_platform(first(node, "platform", "channel", "service"))
            status = str(first(node, "provider_status", "status", "state", "execution_state") or "").lower()
            published_at = first(node, "published_at", "sent_at", "executed_at", "scheduled_at", "due_at")
            product_id = first(node, "product_id", "opportunity_id", "candidate_id", "slug")
            execution_id = first(node, "scheduler_execution_id", "execution_id", "id")

            # Provider truth: require a provider post id and a state that represents a durable provider-side execution.
            durable = status in {"published", "sent", "scheduled", "sending", "success", "created", "confirmed"}
            if not (source_hash and provider_post_id and platform and durable):
                continue

            key = (str(source_hash), platform, str(provider_post_id))
            rows[key] = {
                "source_hash": str(source_hash),
                "product_id": str(product_id) if product_id else None,
                "lifecycle_state": "published",
                "published_at": str(published_at) if published_at else datetime.now(timezone.utc).isoformat(),
                "published_platforms": [platform],
                "scheduler_execution_ids": [str(execution_id)] if execution_id else [],
                "provider_post_ids": [str(provider_post_id)],
                "provider": "buffer",
                "idempotency_key": f"{source_hash}:{platform}:{provider_post_id}",
            }
    return list(rows.values())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", action="append", default=[])
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    paths = [Path(p) for p in args.input]
    rows = extract(paths)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"version": "top100-publish-reconcile-v1", "published": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"published_records": len(rows)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
