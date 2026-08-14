# Social Scheduler — Buffer Autopilot

Safety-first, fully automated Buffer scheduler for the Aug–Nov 2026 social portfolio:

- CoffeeGo AI
- CabinPilot Travel
- CabinPilot Smart Savings
- Λύσεις που Αξίζουν / Biz Box Solver
- Travel AI / GreekVibes
- Red Raven Eyewear

## Fast interaction — add a new tracking URL

You do not need to edit JSON manually.

### In ChatGPT

Use:

`NEW TRACKING URL: <exact URL> | BRAND: <brand> | ANGLE: <hook> | DATE: YYYY-MM-DD HH:MM | PLATFORMS: instagram,facebook,tiktok | ASSET: auto-card`

### In GitHub

Open **Issues → New issue → ➕ New Tracking URL**.

The intake pipeline preserves the exact tracking URL, creates/reuses a tracking-source ID, creates one deterministic campaign, generates different copy for each selected platform, creates a unique fallback PNG when `auto-card` is selected, validates the repo, and commits the desired campaign state. Editing the same issue updates the same campaign instead of producing duplicates.

Tracking intake never publishes directly. Buffer scheduling remains owned exclusively by the `Social Scheduler` workflow.

See `docs/INTERACTION.md` for the full contract.

## What it does

Every hour the GitHub Action runs the scheduler, which:

1. authenticates to the current Buffer GraphQL API;
2. verifies the configured organization and all three connected channels;
3. reads `scheduled`, `sending`, `error`, `sent`, `draft`, `needs_approval` posts and Buffer Ideas;
4. creates missing durable Ideas from `config/backlog.json`;
5. deduplicates against exact executions already sent/scheduled/sending;
6. protects against the 2026-08-14 early-publish failure mode;
7. fills only available slots in the rolling Buffer queue, never exceeding **10**;
8. uses only `customScheduled` for campaign backlog — `shareNow` and `shareNext` are rejected;
9. blocks Instagram/TikTok when media is missing/unreachable;
10. blocks claim-sensitive campaigns until current facts are verified;
11. interleaves brands so one brand does not monopolize the active queue.

Buffer's current API is GraphQL at `https://api.buffer.com` and uses a Bearer API key.

## One-time setup

1. In Buffer, create an API key under **Settings → API**.
2. In this GitHub repository, add Actions secret **`BUFFER_API_KEY`**.
3. Upload preferred supplied creatives into `/assets`, or use the tracking intake `auto-card` fallback.
4. Run **Actions → Social Scheduler → Run workflow → dry-run** once.
5. If the output is clean, run `live`. The hourly schedule will then maintain the rolling queue automatically.

See `docs/BUFFER_SETUP.md`, `docs/OPERATIONS.md`, `docs/MASTER_SOURCE.md`, `docs/INTERACTION.md`, and `docs/TASKS.md`.

## Local test

```bash
python -m unittest discover -s tests -v
```

## Local dry-run/live

```bash
export BUFFER_API_KEY='...'
python -m src.main --mode dry-run
python -m src.main --mode live
```

## Safety note

Queue fullness is never prioritized over correctness. If media or fresh verification is unavailable, the scheduler leaves capacity unused rather than publishing unsafe or malformed content.
