# Social Scheduler — Buffer Autopilot

Safety-first, fully automated Buffer scheduler for the Aug–Nov 2026 social portfolio:

- CoffeeGo AI
- CabinPilot Travel
- CabinPilot Smart Savings
- Λύσεις που Αξίζουν / Biz Box Solver
- Travel AI / GreekVibes
- Red Raven Eyewear

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

Buffer's current API is GraphQL at `https://api.buffer.com` and uses a Bearer API key. The implementation follows the current official Buffer developer model for organizations, channels, Ideas and `createPost(customScheduled)`.

## One-time setup

1. In Buffer, create an API key under **Settings → API**.
2. In this GitHub repository, add Actions secret **`BUFFER_API_KEY`**.
3. Upload the supplied PNG creatives into `/assets` using the exact filenames in `config/backlog.json`.
4. Run **Actions → Social Scheduler → Run workflow → dry-run** once.
5. If the output is clean, run `live`. The hourly schedule will then maintain the rolling queue automatically.

See `docs/BUFFER_SETUP.md`, `docs/OPERATIONS.md`, and `docs/MASTER_SOURCE.md`.

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
