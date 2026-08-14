# Deployment status — 2026-08-14

## Repository state

The production scheduler stack is committed to `main`:

- Buffer GraphQL client with explicit rate-limit circuit breaking
- six-brand Aug–Nov campaign backlog
- organization/channel validation
- reconciliation across draft / needs_approval / scheduled / sending / sent / error
- exact-execution deduplication using channel + normalized text and Buffer Idea IDs
- rolling active queue capped at 10
- brand interleaving
- `customScheduled`-only campaign publishing
- explicit ban on `shareNow` / `shareNext`
- conservative handling of existing Buffer errors (no blind retry)
- 26 Aug CabinPilot Smart Savings Facebook hold
- fresh-verification gates for Red Raven and deal-sensitive content
- media validation for Instagram/TikTok
- automatic recovery of original media from existing Buffer Ideas into `/assets`
- hourly GitHub Actions workflow
- unit tests and operational documentation

## Activation state

**Code: READY**  
**GitHub Action: ACTIVE**  
**`BUFFER_API_KEY` secret: PRESENT / confirmed by GitHub Actions**  
**Current Buffer API state: RATE LIMITED / SAFE DEFER**

A Buffer Smoke workflow run on 2026-08-14 confirmed that the repository secret is present and available to the runner. The first live read then received HTTP 429 with `Retry-After=51900` seconds.

The observed retry window ends at:

- `2026-08-15T10:01:29Z`
- `2026-08-15 13:01:29 Europe/Athens`

The scheduler now treats this condition as a safe defer rather than a deployment failure. While Buffer is throttled it performs **no Buffer writes**, does not attempt asset recovery, and does not run the scheduling mutation path.

Because the production workflow runs hourly at minute 17, the first normal scheduled attempt after the observed retry window is **2026-08-15 13:17 Europe/Athens**, subject to normal GitHub Actions scheduling delay.

## Verified smoke behavior

The rate-limit-aware Buffer Smoke run completed successfully with:

- unit tests: PASS
- `BUFFER_API_KEY` secret presence: PASS
- Buffer preflight: classified `rate_limited`
- asset recovery: SKIPPED
- repository asset writes: SKIPPED
- scheduler dry-run/write path: SKIPPED
- overall job result: SUCCESS

This is the intended behavior: external Buffer throttling must never cause early publishing, duplicate recovery, or repeated mutation attempts.

## Media bootstrap

When Buffer becomes available, `scripts/sync_idea_assets.py` reads existing Buffer Ideas and downloads original image media for backlog entries that already have saved Idea IDs. The workflow then commits recovered images into `/assets` before running the scheduler.

Campaigns whose creative does not yet exist in Buffer and is not committed under `/assets` remain safely blocked on Instagram/TikTok. Facebook may publish text-only content only where the campaign configuration permits it.

## Buffer API availability

The API is currently throttled at the account/API level. Because the preflight cannot yet complete an authenticated account read, the API key's **presence** is confirmed but successful Buffer authentication and current queue counts cannot be fully verified until the rate-limit window clears.

No claim is made yet about the live scheduled queue count, Ideas count, current errors, or the Travel AI 12 Sep execution. Those will be reconciled from Buffer as soon as the API accepts reads again.

## Writer ownership

The separate ChatGPT `Social Campaign Scheduler` writer has been disabled to avoid competing scheduling writers. Reporting/monitoring/recovery safety coverage can remain available while GitHub owns the production scheduler path.

Once a successful post-throttle Buffer reconciliation completes, the GitHub scheduler is the canonical queue-filling writer. Avoid enabling a second independent queue-filling scheduler, because that would introduce race and duplication risk.
