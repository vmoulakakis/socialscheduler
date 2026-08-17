# OpenPost publisher backend

SocialScheduler can use OpenPost as an execution backend for **already-approved SocialMarket outbox jobs**. OpenPost does not choose products, rewrite approved content, or bypass SocialMarket quality controls.

## Data flow

```text
SocialMarket approved publish.outbox
        |
        v
SocialScheduler
        |
        +-- PUBLISHER_BACKEND=buffer   (existing default)
        +-- PUBLISHER_BACKEND=postiz   (existing alternative)
        +-- PUBLISHER_BACKEND=openpost (new)
                                  |
                                  v
                         OpenPost Publication
                         create -> reconcile -> schedule
                                  |
                                  v
                         Facebook / Instagram / TikTok
```

The OpenPost adapter preserves the approved `caption`, `hashtags`, `tracking_url`, `media_url`, platform and `scheduled_for`. It explicitly sets `random_delay_minutes=0` so OpenPost does not shift the SocialMarket-approved schedule.

## Required OpenPost setup

1. Run an OpenPost instance and expose its REST API. `OPENPOST_API_URL` must include the REST prefix, normally `https://<host>/api/v1`.
2. Sign in to OpenPost and connect the required social accounts through OpenPost OAuth.
3. Identify the OpenPost workspace ID and the connected social-account ID for each channel used by SocialScheduler.
4. Create an OpenPost API token with `api:write` scope. Prefer a token limited to the SocialScheduler workspace.

## GitHub Actions configuration

Configure these in the `vmoulakakis/socialscheduler` repository.

### Secret

- `OPENPOST_API_TOKEN` — OpenPost API token. Never put it in repository variables or source code.

### Variables

- `OPENPOST_API_URL` — example shape: `https://<openpost-host>/api/v1`
- `OPENPOST_WORKSPACE_ID`
- `OPENPOST_ACCOUNT_FACEBOOK` — optional if Facebook is not used
- `OPENPOST_ACCOUNT_INSTAGRAM` — optional if Instagram is not used
- `OPENPOST_ACCOUNT_TIKTOK` — optional if TikTok is not used
- `OPENPOST_MEDIA_MAX_BYTES` — adapter safety cap; default `104857600` (100 MiB)
- `OPENPOST_MEDIA_READY_TIMEOUT_SECONDS` — default `90`

At least one `OPENPOST_ACCOUNT_*` value is required when the OpenPost backend is selected.

## Safe activation sequence

Do not switch the scheduled workflow to OpenPost immediately.

1. Keep the repository/default `PUBLISHER_BACKEND` on `buffer`.
2. Configure OpenPost and connect the real social accounts.
3. Manually run **Social Scheduler** with:
   - `publisher_backend = openpost`
   - `mode = dry-run`
   - `content_source = socialmarket_outbox`
4. Confirm the dry run reports the intended workspace, configured account mappings and expected approved-job distribution. Dry-run performs no OpenPost mutations and does not lease outbox jobs.
5. Only after OpenPost connectivity/account readiness and the upstream SocialMarket publishing quality gate are both healthy, run one controlled `openpost + live` execution.
6. Verify the OpenPost publication, its exact schedule/media/copy/tracking URL, and the SocialMarket outbox ACK before changing the recurring backend.

## Duplicate-safety model

Every OpenPost publication created by this adapter carries metadata:

```json
{
  "source": "socialscheduler",
  "publisher": "openpost",
  "socialmarket_job_id": "<outbox job id>",
  "platform": "facebook|instagram|tiktok"
}
```

Before creating a publication, the adapter searches OpenPost for the same SocialMarket job ID and platform.

- one existing scheduled/published publication -> reconcile and ACK; do not create another
- more than one matching publication -> fail closed
- ambiguous create/schedule network response -> read/reconcile before any further mutation
- deterministic validation failure (HTTP 400/422) -> may be ACKed failed
- auth, server, conflict or ambiguous network failure -> do not blindly retry the write; leave the SocialMarket lease to expire for safe later reconciliation

## Media flow

For an approved `media_url`, SocialScheduler:

1. downloads the approved asset subject to the adapter safety-size cap;
2. creates an OpenPost media upload session;
3. uploads to the exact target returned by OpenPost;
4. completes the upload session;
5. waits for OpenPost media readiness;
6. references the returned OpenPost `media_id` in the Publication.

Instagram and TikTok jobs are blocked if no media URL is present. This avoids publishing an invalid or materially different post.

## OpenPost native publication lifecycle used

The adapter uses OpenPost's native REST lifecycle rather than emulating Buffer objects:

```text
POST /publications
POST /publications/{id}/schedule
```

The schedule action includes the publication revision and `execution_intent=production`. The initial publication stores the approved `scheduled_at`; the separate schedule action performs the actual OpenPost enqueue.

## Rollback

OpenPost is provider-neutral and opt-in. Returning to Buffer requires only selecting/configuring:

```text
PUBLISHER_BACKEND=buffer
```

No SocialMarket content/ranking logic needs to change.
