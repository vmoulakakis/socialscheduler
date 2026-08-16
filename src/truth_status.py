from __future__ import annotations

from collections import Counter
from typing import Any, Iterable


def queue_slo(active_queue: int, queue_limit: int) -> dict[str, Any]:
    limit = max(1, int(queue_limit))
    active = max(0, int(active_queue))
    fill_rate = min(100.0, round((active / limit) * 100.0, 2))
    missing = max(0, limit - active)
    return {
        "target_fill_rate_pct": 100.0,
        "fill_rate_pct": fill_rate,
        "active_queue": active,
        "queue_limit": limit,
        "missing_slots": missing,
        "met": missing == 0,
        "severity": "OK" if missing == 0 else "CRITICAL",
    }


def action_counts(actions: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(action.get("type") or "unknown") for action in actions)
    return dict(sorted(counts.items()))


def incident_reason(*, missing_slots: int, outbox_jobs_received: int, blocked_actions: int, buffer_errors: int) -> str:
    if missing_slots <= 0:
        return "none"
    if buffer_errors > 0:
        return "buffer_error"
    if outbox_jobs_received <= 0:
        return "approved_socialmarket_supply_shortage"
    if blocked_actions > 0:
        return "approved_jobs_blocked_by_safety_or_media_truth"
    return "queue_refill_incomplete"
