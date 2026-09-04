# SocialScheduler — Safety-First Autonomous Publishing

> Execution plane for approved social publishing intent. SocialScheduler validates, deduplicates, schedules, reconciles and fails closed when media or evidence is not trustworthy enough.

**Portfolio:** https://dealora-ai.com/portfolio  
**Upstream intelligence:** https://github.com/vmoulakakis/Socialmarket

## System role

SocialScheduler is intentionally **not another content brain**. SocialMarket owns canonical intelligence, content and publishing intent; SocialScheduler owns execution.

```text
SocialMarket AI
  approved publishing intent
          ↓
     publish.outbox
          ↓
   SocialScheduler
          ↓
validation / dedupe / timing / media gates
          ↓
       Buffer
          ↓
Instagram · Facebook · TikTok
          ↓
provider reconciliation / execution state
```

This boundary prevents two independent systems from inventing campaigns, tracking URLs, merchant data or schedules.

## What runs autonomously

Scheduled GitHub Actions maintain the operational loop. Depending on the active workflow/configuration, the system:

1. authenticates to Buffer's GraphQL API;
2. verifies the configured organization and connected channels;
3. reads current scheduled/sending/error/sent/draft/approval state;
4. materializes approved durable work;
5. deduplicates against exact executions already sent or in flight;
6. protects against early-publish failure modes;
7. fills only safe queue capacity;
8. rejects unsafe immediate-publish semantics for campaign backlog;
9. blocks media-dependent platforms when assets are missing/unreachable;
10. blocks claim-sensitive content until current facts are verified;
11. interleaves brands so one campaign family cannot monopolize the active queue;
12. reconciles provider state back into the execution record.

## Fast intake contract

For operator-driven additions, the repository supports a deterministic tracking-URL intake pattern rather than free-form campaign mutation.

```text
NEW TRACKING URL: <exact URL> | BRAND: <brand> | ANGLE: <hook> | DATE: YYYY-MM-DD HH:MM | PLATFORMS: instagram,facebook,tiktok | ASSET: auto-card
```

The intake path preserves the exact tracking URL, reuses stable identities, generates platform-specific copy/assets and updates the same campaign rather than creating uncontrolled duplicates.

Tracking intake never publishes directly.

See [`docs/INTERACTION.md`](docs/INTERACTION.md).

## Safety invariants

- queue fullness never outranks correctness
- missing/unreachable media can block execution
- unverified sensitive claims can block execution
- duplicate detection is deterministic
- scheduling state is reconciled against the provider
- execution credentials belong here, not in SocialMarket
- real provider secrets remain in GitHub Actions/runtime secrets, never committed

## Operational docs

- [`docs/BUFFER_SETUP.md`](docs/BUFFER_SETUP.md)
- [`docs/OPERATIONS.md`](docs/OPERATIONS.md)
- [`docs/MASTER_SOURCE.md`](docs/MASTER_SOURCE.md)
- [`docs/INTERACTION.md`](docs/INTERACTION.md)
- [`docs/TASKS.md`](docs/TASKS.md)

## Local validation

```bash
python -m unittest discover -s tests -v
```

## Local dry-run / live

```bash
export BUFFER_API_KEY='...'
python -m src.main --mode dry-run
python -m src.main --mode live
```

## Portfolio context

| System | Responsibility |
| --- | --- |
| [SocialMarket AI](https://github.com/vmoulakakis/Socialmarket) | evidence, opportunity, content and canonical intent |
| [Dealora](https://dealora-ai.com) | consumer buying decisions |
| [AI Greece Travel](https://github.com/vmoulakakis/travel_ai) | destination decisions |
| **SocialScheduler** | safe autonomous execution |

The engineering goal is not maximum posting volume. It is **reliable execution of already-approved intent with explicit failure gates**.
