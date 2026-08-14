# Deployment status — 2026-08-14

## Repository state

The production scheduler stack is committed to `main`:

- Buffer GraphQL client with 429 retry/backoff
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
**GitHub Action: CONFIGURED**  
**Live Buffer publishing from GitHub: BLOCKED UNTIL `BUFFER_API_KEY` SECRET EXISTS**

The GitHub connector available during implementation does not expose repository-secret creation, so the Buffer API key cannot be safely inserted programmatically from this session.

Required one-time repository secret:

`BUFFER_API_KEY`

Create the API key in Buffer Settings → API, then save it in GitHub repository Settings → Secrets and variables → Actions → New repository secret.

Never commit the key to the repository.

## Media bootstrap

On the first authenticated workflow run, `scripts/sync_idea_assets.py` reads existing Buffer Ideas and downloads the original image media for backlog entries that already have saved Idea IDs. The workflow then commits those recovered images into `/assets` before running the scheduler.

Campaigns whose creative does not yet exist in Buffer and is not committed under `/assets` remain safely blocked on Instagram/TikTok. Facebook may publish text-only content where the campaign allows it.

## Buffer API availability at implementation time

A live Buffer connector check on 2026-08-14 returned HTTP 429 with a long `Retry-After`, so no claim is made here about the current live queue count. The GitHub scheduler contains its own 429 retry/backoff and will reconcile live state when the API accepts requests.

## Writer ownership

Until the GitHub workflow has a valid `BUFFER_API_KEY` and completes a successful reconciliation run, existing ChatGPT recovery/monitoring automations should remain available as safety coverage.

After the GitHub scheduler is confirmed live, avoid two independent scheduling writers. Keep reporting/monitoring tasks, but disable any separate automation whose job is to independently fill the Buffer queue. This prevents race conditions and duplicate scheduling.
