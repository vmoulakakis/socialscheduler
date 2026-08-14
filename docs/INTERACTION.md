# Interaction model — Task 1 control layer

The Social Media Autopilot has one canonical scheduling writer: the GitHub `Social Scheduler`. Human/ChatGPT interaction must change desired campaign data, not bypass the scheduler and write directly to Buffer.

## Fastest interaction: ChatGPT

Send a message in this project using this compact format:

`NEW TRACKING URL: <exact URL> | BRAND: <brand> | ANGLE: <hook> | DATE: YYYY-MM-DD HH:MM | PLATFORMS: instagram,facebook,tiktok | ASSET: auto-card`

The exact tracking URL must be preserved unless the user explicitly provides a supported sub-ID/UTM template. Never append arbitrary query parameters to opaque affiliate/tracking URLs.

## GitHub interaction: New Tracking URL issue

Use the repository issue form **➕ New Tracking URL**.

Required inputs:
- exact tracking URL
- brand
- campaign angle/hook
- target Europe/Athens date/time
- platforms
- asset mode
- claim sensitivity

The `Tracking URL Intake` workflow then:
1. validates and preserves the URL;
2. creates/reuses a `tracking_source_id` in `config/tracking_sources.json`;
3. creates a deterministic request under `inbox/tracking/`;
4. creates or updates one deterministic campaign in `config/backlog.json`;
5. creates an automatic fallback PNG card when `auto-card` is selected;
6. creates platform-specific Instagram/Facebook/TikTok copy;
7. marks claim-sensitive campaigns with `requires_verification: true`;
8. runs compile/config/unit validation;
9. commits the result to `main`;
10. comments the campaign ID back on the issue.

Editing the same issue updates the same campaign ID instead of creating a duplicate.

## Asset modes

### `auto-card`
Creates a unique 1080×1350 PNG fallback card from brand + campaign angle + destination domain. This is for reliable automation; supplied/generated high-quality brand creatives should still be preferred when available.

### `existing-file`
Uses an exact filename already present under `/assets`. The workflow fails rather than silently substituting another image when the file is missing.

### `manual-review`
Creates the campaign record but places all selected services on hold until a valid asset is supplied.

## Tracking URL safety

Default tracking mode is `opaque`:
- preserve the URL byte-for-byte as submitted;
- do not invent UTM parameters;
- do not invent affiliate sub-IDs;
- unique identity comes from repo campaign/execution IDs, not URL mutation.

If a merchant/affiliate network later provides an explicit sub-ID template, add that as a separate supported tracking mode with tests before using it.

## Writer ownership

- GitHub `Social Scheduler`: Buffer scheduling writer.
- Tracking intake: desired-state/backlog writer only; it does **not** publish or schedule directly.
- Silent Monitor: read-only.
- Daily Social Excel: read-only reporting.
- ChatGPT `Social Campaign Scheduler`: disabled.
- Social Queue Recovery: disabled.

This separation prevents race conditions and accidental early publishing.
