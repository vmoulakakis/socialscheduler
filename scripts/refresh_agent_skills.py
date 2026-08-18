#!/usr/bin/env python3
"""Rebuild skills/MASTER_SKILLS.md from stable role cards + live operating telemetry."""
from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://rpfadpdnnxequgvdcfoq.supabase.co").rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "sb_publishable_NkMSCtURWbZcA8MCY1H5sA_W_G10WYD")
ROLE_CARDS = Path("skills/ROLE_CARDS.md")
MASTER = Path("skills/MASTER_SKILLS.md")


def fetch_context():
    url = f"{SUPABASE_URL}/rest/v1/socialscheduler_agent_nightly_context_v?select=*&limit=1"
    req = urllib.request.Request(url, headers={"apikey": SUPABASE_ANON_KEY, "authorization": f"Bearer {SUPABASE_ANON_KEY}", "accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        rows = json.loads(r.read().decode("utf-8"))
    return rows[0] if rows else {}


def priorities(c):
    out = []
    rankings = int(c.get("durable_product_rankings") or 0)
    assets = int(c.get("missing_assets") or 0)
    measured = int(c.get("measured_feedback_rows") or 0)
    pipeline = c.get("pipeline_by_platform") or {}
    if rankings == 0:
        out.append("CRITICAL — Product Intelligence durable rankings are still zero; keep product-ranking status RED and use existing canonical inventory without pretending ranked-product evidence exists.")
    else:
        out.append(f"Product Intelligence has {rankings} durable rankings; allow ranked products to compete through opportunity scoring, not automatic first place.")
    if assets > 0:
        out.append(f"Creative backlog: {assets} canonical items are missing media; Asset Studio should prioritize the highest opportunity scores first.")
    else:
        out.append("Creative backlog is clear; reuse strong source assets before generating new fallback posters.")
    if measured < 20:
        out.append(f"Only {measured} measured feedback rows: timing/selection should still lean on commercial/freshness priors and avoid overfitting.")
    elif measured < 100:
        out.append(f"Measured feedback rows: {measured}. Continue shifting weight toward observed performance while preserving exploration.")
    else:
        out.append(f"Measured feedback rows: {measured}. Feedback is mature enough to carry major selection/timing weight, with exploration still capped.")
    for p in ("facebook", "instagram", "tiktok", "linkedin"):
        n = int(pipeline.get(p) or 0)
        floor = 3 if p == "linkedin" else 10
        if n < floor:
            out.append(f"{p.title()} pipeline {n} is below safety floor {floor}; refill opportunity inventory before increasing experimentation.")
    return out


def main():
    context = fetch_context()
    role_text = ROLE_CARDS.read_text(encoding="utf-8")
    now = datetime.now(timezone.utc).isoformat()
    p = priorities(context)
    weights = context.get("opportunity_weights") or {}
    feedback = context.get("provider_feedback_30d") or []

    lines = [
        "# SocialScheduler MASTER SKILLS — Live Operating Manual",
        "",
        f"Generated automatically: `{now}`",
        "",
        "> This file is rebuilt nightly. Stable safety/role doctrine comes from `ROLE_CARDS.md`; the operating context comes from live SocialScheduler telemetry. User ideas are evaluated as hypotheses, not copied into policy automatically.",
        "",
        "## Tonight's Operating Priorities",
    ]
    for x in p:
        lines.append(f"- {x}")
    lines += [
        "",
        "## Current Opportunity Weights",
        "",
        "```json",
        json.dumps(weights, ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
        "## Live Pipeline Snapshot",
        "",
        "```json",
        json.dumps(context.get("pipeline_by_platform") or {}, ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
        "## 30-Day Provider Feedback Evidence",
        "",
        "```json",
        json.dumps(feedback, ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
        "## Live Counts",
        "",
        f"- Canonical ready content: **{int(context.get('content_ready') or 0)}**",
        f"- Missing assets: **{int(context.get('missing_assets') or 0)}**",
        f"- Feedback ledger rows: **{int(context.get('feedback_rows') or 0)}**",
        f"- Measured feedback rows: **{int(context.get('measured_feedback_rows') or 0)}**",
        f"- Orchestration decisions: **{int(context.get('orchestration_decisions') or 0)}**",
        f"- Durable product rankings: **{int(context.get('durable_product_rankings') or 0)}**",
        "",
        "---",
        "",
        role_text,
        "",
    ]
    MASTER.parent.mkdir(parents=True, exist_ok=True)
    MASTER.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"ok": True, "master": str(MASTER), "priorities": len(p), "generated_at": now}, ensure_ascii=False))


if __name__ == "__main__":
    main()
