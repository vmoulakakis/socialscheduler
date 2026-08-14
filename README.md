# Social Scheduler — Buffer Execution Engine

Safety-first publishing executor for Facebook, Instagram and TikTok.

**Production content is owned exclusively by SocialMarket AI.** SocialScheduler does not discover products, invent campaigns, choose brands, or maintain a second production content plan.

## Production contract

`SocialMarket AI → publishing_outbox → SocialScheduler → Buffer → FB / IG / TikTok → status back to SocialMarket`

SocialMarket stores the canonical brand/site, content item, creative, caption, platform payload and intended publishing time. SocialScheduler receives only approved outbox executions.

## What the hourly workflow does

1. authenticates to Buffer;
2. verifies the configured organization and connected channels;
3. obtains a short-lived GitHub Actions OIDC token;
4. authenticates to the SocialMarket `publishing-outbox` Edge Function;
5. claims only explicitly dated, approved outbox jobs;
6. reads current Buffer `scheduled`, `sending`, `error`, `sent`, `draft` and `needs_approval` posts;
7. deduplicates against executions already consumed;
8. protects against early publication and forbids `shareNow` / `shareNext`;
9. fills only available slots in the rolling Buffer queue, never exceeding **10**;
10. blocks Instagram/TikTok when media is missing or unreachable;
11. interleaves brands so one brand does not monopolize the active queue;
12. acknowledges Buffer post IDs/status back to SocialMarket;
13. maps Buffer `sent` → SocialMarket `published` and Buffer `error` → SocialMarket `failed`.

## Authentication

No SocialMarket shared secret is stored in this public repository.

GitHub Actions has `id-token: write` and requests an OIDC JWT with audience `socialmarket-ai`. The SocialMarket Edge Function validates:
- issuer `https://token.actions.githubusercontent.com`;
- audience `socialmarket-ai`;
- repository `vmoulakakis/socialscheduler`;
- production ref `refs/heads/main`.

Buffer still uses the repository secret `BUFFER_API_KEY`.

## Legacy backlog

`config/backlog.json` is retained only as **rollback/archive input**. Scheduled production runs use:

`CONTENT_SOURCE=socialmarket_outbox`

A manual emergency workflow may temporarily select `legacy_backlog`, but it is not the production source of truth.

The one-time workflow **Migrate Legacy Backlog to SocialMarket** imports the existing backlog idempotently into SocialMarket. Held or verification-sensitive campaigns are not made executable automatically.

## Safety invariants

- never publish a future-dated item early;
- never invent a publishing time;
- only `customScheduled` is allowed;
- queue fullness is never more important than correctness;
- no blind retries after ambiguous Buffer errors;
- Instagram/TikTok require valid media;
- an outbox lease expires safely if a workflow crashes before scheduling;
- one canonical content item may have platform-specific execution rows, but there is no independent scheduler-authored campaign copy.

## Local tests

```bash
python -m unittest discover -s tests -v
```

Legacy local mode remains available for rollback testing:

```bash
export BUFFER_API_KEY='...'
CONTENT_SOURCE=legacy_backlog python -m src.main --mode dry-run
```

Production SocialMarket mode requires GitHub Actions OIDC and therefore is intended to run inside the workflow.
