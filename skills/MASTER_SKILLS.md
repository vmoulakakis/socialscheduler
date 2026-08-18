# SocialScheduler MASTER SKILLS — Live Operating Manual

Generated/seeded from production telemetry on `2026-08-18`.

> This file is authoritative for agent operation. It is rebuilt nightly from live telemetry plus `skills/ROLE_CARDS.md`. User ideas are treated as hypotheses to evaluate, not automatically converted into policy.

## Tonight's Operating Priorities
- **CRITICAL:** Product Intelligence durable rankings are `0`; keep that subsystem RED until real ranked products persist.
- **Creative backlog:** `96` canonical items have tracking URLs but no media. Zero-Cost Asset Studio must generate highest-opportunity assets first.
- **Feedback maturity:** `16` feedback rows exist, only `5` currently have non-zero weighted evidence. Do not overfit; retain stronger commercial/freshness priors.
- **Pipeline floors are healthy:** Facebook `74`, Instagram `15`, TikTok `14`, LinkedIn `19` pipeline jobs over the active 7-day horizon.
- **Rotation remains mandatory:** new products receive an exploration boost, but the current new-product share cap is `30%` and brand daily cap is `4`.

## Current Opportunity Weights
```json
{
  "freshness_weight": 24,
  "commercial_weight": 24,
  "feedback_weight": 10,
  "asset_weight": 12,
  "source_weight": 8,
  "urgency_weight": 8,
  "fatigue_weight": 10,
  "new_product_share_cap": 0.30,
  "brand_daily_cap": 4
}
```

## Current Evidence Snapshot
```json
{
  "content_ready": 131,
  "missing_assets": 96,
  "feedback_rows": 16,
  "measured_feedback_rows": 5,
  "orchestration_decisions": 109,
  "durable_product_rankings": 0,
  "pipeline_by_platform": {
    "facebook": 74,
    "instagram": 15,
    "tiktok": 14,
    "linkedin": 19
  }
}
```

---

See `skills/ROLE_CARDS.md` for the stable role doctrine covering:
- Opportunity Strategist
- Product Scout
- Growth Copy Chief
- Creative Director
- Rotation & Fatigue Manager
- Channel & Provider Router
- Feedback Scientist
- Audit Guardian
- Skill Curator

## Master Principle
**The scheduler is an opportunistic portfolio optimizer, not FIFO, not “newest wins,” and not a blind implementation of suggestions.**
