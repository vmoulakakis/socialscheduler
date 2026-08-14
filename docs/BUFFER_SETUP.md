# Buffer production setup

## Required secret

Create one GitHub Actions repository secret:

- `BUFFER_API_KEY` — Buffer API key from Buffer **Settings → API**.

The key must never be committed. Buffer's current API uses `Authorization: Bearer <key>` against `https://api.buffer.com`.

## Fixed organization and channels

Organization: `My Organization` (`68a86463018d512de98d6315`), timezone `Europe/Athens`.

- Facebook — Sales for All — `6a7c1fa2b2d9d57743615a1c`
- TikTok — billmtiktoker_ai — `6a7c20eab2d9d57743615efa`
- Instagram — vassilis1969 — `68a864cf8e37dc1a589afa8b`

The scheduler verifies these IDs are still connected before it writes anything.

## Assets

Put supplied PNGs under `/assets` using the exact filenames already referenced by `config/backlog.json`.
Because this repository is public, the scheduler can resolve them as stable `raw.githubusercontent.com` HTTPS URLs. Instagram/TikTok executions are blocked until their image URL is reachable.

## Workflow

`.github/workflows/social-scheduler.yml` runs hourly at minute 17 and supports manual `workflow_dispatch` in `dry-run` or `live` mode.

The workflow deliberately fails when `BUFFER_API_KEY` is missing. That is the only secret required for Buffer publishing.
