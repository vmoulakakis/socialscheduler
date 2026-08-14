# Social Scheduler Architecture

## Canonical ownership

### Desired campaign state
The repository is the canonical desired-state source for scheduling:
- `config/backlog.json` — campaign executions, dates, platforms, copy, media references and holds
- `config/settings.json` — queue limits, timezone and safety rules
- `config/channels.json` — configured Buffer destination channel IDs

`docs/MASTER_SOURCE.md` is a human-readable project reference. It is not the live execution state and may lag operational changes.

### Live execution state
Buffer is the live execution source for:
- Ideas
- drafts
- scheduled posts
- sending posts
- sent posts
- errors

The scheduler must reconcile Buffer before making any scheduling mutation.

## Single-writer rule

The GitHub Actions workflow `.github/workflows/social-scheduler.yml` is the sole automated writer allowed to create or schedule campaign content in Buffer.

No ChatGPT automation, recovery task, monitor, report, or second scheduler may independently fill the Buffer queue or create/reschedule/publish campaign executions while GitHub owns production scheduling.

This prevents race conditions, duplicate scheduling and recurrence of the 2026-08-14 early-publish failure mode.

## ChatGPT task roles

- `Social Campaign Scheduler` — disabled; must remain disabled while GitHub is the writer.
- `Social Queue Recovery` — disabled; GitHub reconciliation owns recovery of the campaign queue.
- `Social Portfolio Silent Monitor` — enabled as read-only monitoring only; zero Buffer mutation authority.
- `Daily Social Report` — enabled for reporting only; must not independently schedule or refill the queue.

Unrelated project automations are outside this architecture.

## Data flow

`GitHub desired state -> safety/reconciliation engine -> Buffer live state -> Instagram / Facebook / TikTok`

Monitoring and reporting observe this flow but do not write to Buffer.

## Rule for conflicts

If repository desired state and Buffer live state differ, the scheduler must first classify the live Buffer execution before acting. Existing sent, sending or scheduled executions are never recreated blindly. Queue correctness is more important than queue fullness.
