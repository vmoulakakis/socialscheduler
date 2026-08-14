# Social Scheduler task map

This is the working task model for the repository. Tasks are ordered by dependency and safety impact.

## T1 — Control architecture ✅
- GitHub is desired-state source.
- Buffer is live execution state.
- GitHub Social Scheduler is the only Buffer scheduling writer.
- Silent Monitor and Daily Social Excel are read-only.

## T1.1 — Tracking URL intake & interaction ✅
- Structured GitHub Issue Form.
- Deterministic tracking source registry.
- Deterministic campaign IDs.
- Exact/opaque URL preservation.
- Platform-specific post variants.
- Automatic fallback social-card asset.
- Claim-sensitive verification gate.
- Idempotent issue edits.

## T1.2 — Daily Excel control report ✅
- Daily read-only Excel report via ChatGPT automation.
- Posted 24h, scheduled next 48h, problems/anomalies, tracking URLs, GitHub scheduler, actions, sources.
- Never fabricate unavailable Buffer state.

## T2 — GitHub Actions hardening ⏭️
- cron/timezone review
- permissions least privilege
- concurrency/race review
- workflow failure classification
- artifact/log retention
- action pinning/version policy

## T3 — Buffer API hardening
- authentication validation
- rate-limit/cooldown state
- schema drift detection
- channel validation
- read/write request budget

## T4 — Scheduler engine
- execution identity
- desired-state reconciliation
- late-item policy
- dry-run/live parity

## T5 — Rolling queue ≤10
- chronological eligibility
- fairness by brand/channel
- queue refill policy
- protected capacity rules

## T6 — Deduplication & early-publish protection
- exact execution IDs
- sent/scheduled/error consumption
- duplicate URL/campaign detection
- regression tests for 2026-08-14 incident

## T7 — Campaign backlog Aug–Nov
- coverage by brand/week
- dates/hooks/CTA
- platform-specific variants
- seasonal sequencing

## T8 — Assets
- inventory completeness
- media URL health
- asset recovery
- auto-card quality
- supplied/generated creative preference

## T9 — Platform rules
- Instagram
- Facebook
- TikTok
- format/media/caption constraints

## T10 — Claims verification
- Red Raven official claims
- airline rules
- prices/stock/promotions/offers
- expiration/freshness handling

## T11 — Ideas / Drafts / Scheduled lifecycle
- durable Idea creation
- draft/hold rules
- promotion to rolling queue

## T12 — Error recovery
- 429
- network errors
- Buffer errors
- no blind retry
- classified recovery

## T13 — Monitoring & alerting
- silent normal operation
- actionable alerts only
- scheduler health
- queue/anomaly checks

## T14 — Persistent execution state
- campaign ID
- execution ID
- Buffer post ID
- timestamps/state history
- audit trail

## T15 — Performance optimization
- Buffer metrics
- winner/loser scoring
- hook/timing learning
- tracking-source analysis

## T16 — Production acceptance
- dry-run
- live reconciliation
- queue verification
- duplicate verification
- documentation/handoff
