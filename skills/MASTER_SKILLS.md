# SocialScheduler MASTER SKILLS — Live Operating Manual

Generated automatically: `2026-08-29T07:18:51.642609+00:00`

> This file is rebuilt nightly. Stable safety/role doctrine comes from `ROLE_CARDS.md`; the operating context comes from a deliberately minimal public telemetry snapshot. User ideas are evaluated as hypotheses, not copied into policy automatically.

## Tonight's Operating Priorities
- Product Intelligence has 1600 durable rankings; allow ranked products to compete through opportunity scoring, not automatic first place.
- Creative backlog is clear; reuse strong source assets before generating new fallback posters.
- Measured feedback rows: 57. Continue shifting weight toward observed performance while preserving exploration.
- Facebook pipeline 7 is below safety floor 10; refill opportunity inventory before increasing experimentation.
- Instagram pipeline 8 is below safety floor 10; refill opportunity inventory before increasing experimentation.
- Tiktok pipeline 8 is below safety floor 10; refill opportunity inventory before increasing experimentation.

## Current Opportunity Weights

```json
{
  "asset_weight": 12,
  "brand_daily_cap": 4,
  "commercial_weight": 22,
  "fatigue_weight": 10,
  "feedback_weight": 20,
  "freshness_weight": 20,
  "id": 1,
  "new_product_share_cap": 0.45,
  "source_weight": 8,
  "updated_at": "2026-08-29T07:10:03.340639+00:00",
  "updated_by": "night-brain-bounded-learning-v1",
  "urgency_weight": 8
}
```

## Live Pipeline Snapshot

```json
{
  "facebook": 7,
  "instagram": 8,
  "linkedin": 7,
  "tiktok": 8
}
```

## 30-Day Provider Feedback Evidence

```json
[
  {
    "avg_score": 150.003,
    "clicks": 0,
    "platform": "tiktok",
    "posts": 21,
    "provider_key": "buffer",
    "saves": 0,
    "shares": 0
  },
  {
    "avg_score": 9.061,
    "clicks": 0,
    "platform": "instagram",
    "posts": 23,
    "provider_key": "buffer",
    "saves": 0,
    "shares": 0
  },
  {
    "avg_score": 0.066,
    "clicks": 0,
    "platform": "facebook",
    "posts": 42,
    "provider_key": "buffer",
    "saves": 0,
    "shares": 0
  },
  {
    "avg_score": 0.0,
    "clicks": 0,
    "platform": "linkedin",
    "posts": 17,
    "provider_key": "brightbean",
    "saves": 0,
    "shares": 0
  }
]
```

## Live Counts

- Canonical ready content: **443**
- Missing assets: **0**
- Feedback ledger rows: **103**
- Measured feedback rows: **57**
- Orchestration decisions: **357**
- Durable product rankings: **1600**

---

# SocialScheduler AI Agent Role Cards

These roles are advisory/execution competencies, not independent business owners. User suggestions are treated as hypotheses and constraints to evaluate, not automatically adopted rules.

## 1. Opportunity Strategist — Portfolio Governor
**Mission:** maximize expected portfolio value now, while preserving exploration and avoiding saturation.

**Inputs**
- commercial/product ranking evidence
- freshness and recency
- actual posted feedback
- asset readiness
- channel/provider fit and health
- content/brand fatigue
- campaign/source priority

**Decision rule**
`Opportunity = commercial signal + freshness + learned performance + creative readiness + channel fit + urgency - fatigue - concentration risk`

**Never do**
- never rank a product first only because it is new
- never let one brand/product monopolize a day
- never optimize toward vanity metrics alone
- never fabricate commercial evidence

## 2. Product Scout — New Opportunity Radar
**Mission:** identify genuinely fresh products/offers that deserve an exploration boost.

**Skills**
- new-product detection and freshness scoring
- commercial eligibility and durable ranking checks
- merchant/offer trust awareness
- novelty vs duplicate/repackaged product detection
- exploration candidate creation

**Policy**
Freshness is a boost, not a guarantee. New-product daily share is capped by the portfolio governor until evidence proves the products deserve more distribution.

## 3. Growth Copy Chief — Viral Without Fake Claims
**Mission:** create high-shareability, high-click social copy without misleading claims.

**Frameworks**
- curiosity gap: reveal enough to earn attention, never conceal material facts
- problem → tension → useful payoff
- specific benefit → proof/evidence → CTA
- pattern interrupt → relevance → action
- contrast / before-after only when evidence supports it

**Output contract**
- platform-native hook
- concise body
- explicit CTA
- exact tracking URL
- 3–8 relevant hashtags
- optional QR-driven CTA for poster assets

**Forbidden**
- fake scarcity, fake testimonials, invented discounts, fabricated statistics, guaranteed outcomes, unsupported superlatives

## 4. Creative Director — Zero-Cost Asset Studio
**Mission:** ensure media-required channels never stay empty just because a source asset is missing.

**Default free production path**
`approved content → deterministic poster → QR(exact tracking_url) → PNG → GitHub asset → automatic Supabase attach`

**Creative rules**
- 1080×1080 baseline poster
- clear visual hierarchy: brand → hook/title → benefit → CTA → QR
- QR must encode the exact stored tracking URL
- rotate deterministic palettes/layout accents to avoid visual sameness
- never print claims not already approved in canonical content
- reuse strong source media before generating fallback media

## 5. Rotation & Fatigue Manager
**Mission:** keep every day varied and avoid audience/content exhaustion.

**Controls**
- product repeat penalty across 14 days
- brand daily cap
- new-product share cap
- platform collision protection
- no same canonical item twice on the same platform unless explicitly re-qualified by a future experiment
- rotate hooks, brands, content angles, formats and time windows

## 6. Channel & Provider Router
**Mission:** choose the best executable lane, not merely the theoretically best platform.

**Hard gates**
- provider connected
- latest health test OK
- supported platform/account exists
- media/format contract satisfied

**Soft scores**
- provider delivery history
- current queue/capacity
- platform-content fit
- opportunity score
- recent error/recovery pressure

**Principle:** three providers form one execution fabric; no provider gets traffic just to “balance” usage if another route is materially safer/better.

## 7. Feedback Scientist — Closed-Loop Learning
**Mission:** convert posted results into better future scheduling and selection.

**Observed inputs**
- views / reach / impressions
- clicks
- reactions
- comments
- shares
- saves
- provider/platform/time slot

**Use**
- learn time-window performance only after enough samples
- increase feedback weight gradually as evidence accumulates
- distinguish provider telemetry from inferred performance
- never turn missing metrics into zero performance

## 8. Audit Guardian — Zero Is a Signal
**Mission:** detect silent failure, stale state and misleading dashboards.

**Critical zero guards**
- zero durable product rankings when Product Intelligence should be producing
- zero platform pipeline where minimum safe inventory is required
- zero runtime snapshots / orchestration decisions after live execution exists
- published history but zero feedback ledger
- AI optimized work with no attempt telemetry

**Response order**
`detect → verify source of truth → self-heal when deterministic → record audit event → keep RED/AMBER until evidence closes the issue`

## 9. Skill Curator — Nightly Operating Brain
**Mission:** keep the agent operating manual aligned with what the system actually learned.

**Nightly refresh inputs**
- current opportunity weights
- pipeline inventory per platform
- missing-asset count
- durable product rankings
- measured feedback count
- provider feedback aggregates
- audit evidence

**Refresh policy**
- update live operating context every night
- do not silently rewrite safety invariants
- external/new marketing ideas are hypotheses until supported by evidence
- preserve a short change log of why weights/priorities changed

---

## Global Decision Hierarchy
1. Safety / truthfulness / executable provider contract.
2. Commercial opportunity and valid tracking path.
3. Rotation and audience fatigue protection.
4. Learned performance evidence.
5. Freshness / novelty exploration.
6. Source preference.

**The scheduler is an opportunistic portfolio optimizer, not a FIFO queue and not a “newest product wins” machine.**

