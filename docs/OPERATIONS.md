# Operations and safety model

## Architecture

`config/backlog.json` → Buffer Ideas → reconciliation → rolling active queue (max 10) → publish → next hourly refill.

## Hard invariants

1. Future campaign content is created only with `mode=customScheduled`.
2. `shareNow` and `shareNext` are rejected in code.
3. An exact caption already `sent`, `scheduled`, or `sending` on the same channel is treated as consumed.
4. If a saved Buffer Idea ID is known, any `sent`, `scheduled`, or `sending` post from that same Idea on that same channel is also treated as consumed. This protects against the 2026-08-14 early-publish incident even if the configured target date is still in the future.
5. Instagram and TikTok are blocked when media is missing or unreachable.
6. Fresh-claim campaigns can set `requires_verification=true`; the scheduler will not publish them automatically until that gate is removed after verification.
7. `hold_services` blocks an execution explicitly. The 26 Aug CabinPilot Smart Savings Facebook execution is protected this way.
8. Queue capacity is a ceiling, not a target. The queue may remain under 10 when safety gates block items.

## Late items

Default policy is `defer`: an item whose target time has passed is moved to the same clock time three days in the future. It is never published immediately.

## Recovery

Every run reads all Buffer post states (`draft`, `needs_approval`, `scheduled`, `sending`, `sent`, `error`) plus Ideas before writes. This is the core recovery mechanism.

## Brand rotation

Eligible executions are grouped by brand and interleaved while retaining each execution's scheduled timestamp. This prevents one brand from consuming all queue slots.

## Claim-sensitive content

Red Raven product claims, Black Friday/deals, airline rules, prices, stock, warranty, UV/polarization, promotions and availability must stay behind a verification gate until current official facts are confirmed.

## Media policy

The scheduler uses a stable public media URL before it creates a media post. Assets committed under `/assets` are resolved through `raw.githubusercontent.com`. If a media URL cannot be fetched, Instagram/TikTok remain blocked. Facebook can safely fall back to text-only when appropriate.
