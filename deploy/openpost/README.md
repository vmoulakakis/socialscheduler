# OpenPost self-host for SocialScheduler — no OpenPost subscription

This deployment uses the official open-source OpenPost container in `selfhost` mode.

**OpenPost software subscription: 0 EUR.**

The operator supplies the runtime machine, public HTTPS endpoint, backups and social-provider developer credentials. No OpenPost Hosted/paid plan is used.

## What is already integrated

```text
SocialMarket approved publish.outbox
        |
        v
SocialScheduler
        |
        v
self-hosted OpenPost
        |
        +-- Facebook Page
        +-- Instagram Feed / Story
        +-- TikTok Photo Feed / Video
        +-- LinkedIn Profile / Organization Page
```

Production auto-routing uses Instagram Feed + Story and TikTok Photo Feed with approved static creatives. Instagram Reels and TikTok video execution remain supported only when the outbox contains a real approved video asset. TikTok Story is not exposed as a publishing path because the current OpenPost TikTok adapter does not support it.

## Runtime requirements

- Linux/amd64 Docker host (the official published container is amd64)
- Docker Compose
- persistent disk/volume
- public HTTPS hostname before provider OAuth is configured

A personal computer or home/server machine can run this at zero hosting subscription if it remains powered on and has a stable HTTPS route. A free/owned VPS or other persistent Docker host is also fine. GitHub Actions and Vercel are not substitutes for this long-running persistent service.

## 1. Prepare files

On the Docker machine:

```bash
git clone https://github.com/vmoulakakis/socialscheduler.git
cd socialscheduler/deploy/openpost
cp .env.example .env
```

Edit `.env` and set the real public HTTPS URL:

```env
OPENPOST_APP_URL=https://openpost.your-domain.example
OPENPOST_PUBLIC_URL=https://openpost.your-domain.example
```

Generate unique secrets before the first run:

```bash
openssl rand -base64 32
openssl rand -base64 32
```

Put the two generated values in:

```env
OPENPOST_JWT_SECRET=...
OPENPOST_ENCRYPTION_KEY=...
```

Never commit `.env`.

## 2. Start OpenPost

```bash
docker compose pull
docker compose up -d
docker compose ps
```

Local health endpoint:

```text
http://localhost:8080/api/v1/health
```

The Compose file uses one persistent Docker volume for SQLite and media. Scheduled jobs survive process/container restarts because OpenPost persists them in its database.

## 3. Configure provider apps — still no OpenPost fee

Provider OAuth credentials come directly from the social networks' developer portals, not from a paid OpenPost account.

### Facebook + Instagram

Create/configure a Meta developer app and set the provider credentials in `OPENPOST_PROVIDER_APPS`.

Default callbacks derived from `OPENPOST_APP_URL`:

```text
https://<host>/api/v1/accounts/facebook/callback
https://<host>/api/v1/accounts/instagram/callback
```

OpenPost documents these scopes:

- Facebook: `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`
- Instagram: `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement`, `business_management`

### TikTok

Create/configure a TikTok developer app and add it to `OPENPOST_PROVIDER_APPS`.

Default callback:

```text
https://<host>/api/v1/accounts/tiktok/callback
```

OpenPost documents these scopes:

- `user.info.basic`
- `user.info.profile`
- `video.publish`
- `video.upload`

For static SocialMarket PNG creatives, SocialScheduler converts the asset losslessly to WebP before a TikTok Photo Feed publication, because the OpenPost TikTok adapter accepts JPEG/WebP images for photo posts.

### LinkedIn

OpenPost supports LinkedIn profiles and Organization Pages. Configure:

```env
LINKEDIN_CLIENT_ID=...
LINKEDIN_CLIENT_SECRET=...
```

Default callback:

```text
https://<host>/api/v1/accounts/linkedin/callback
```

For an Organization Page, enable `OPENPOST_LINKEDIN_ORGANIZATIONS_ENABLED=true` only after LinkedIn approves the organization scopes required by the app.

Facebook, Instagram and TikTok media publishing requires publicly reachable HTTPS media URLs.

## 4. Create the first OpenPost account locally

Open the public OpenPost URL in a browser, register the first instance user, create the workspace and connect the social accounts through OAuth.

No OpenPost Hosted signup is required for this self-hosted instance.

## 5. Create a workspace API token

Inside the self-hosted OpenPost UI, create a workspace-bound API token with `api:write` capability for SocialScheduler.

Put that token only in the GitHub Actions secret:

```text
OPENPOST_API_TOKEN
```

Do not commit or paste the token into issues/docs.

## 6. Configure SocialScheduler GitHub Actions

Repository variables:

```text
OPENPOST_API_URL=https://<host>/api/v1
OPENPOST_WORKSPACE_ID=<workspace-id>
OPENPOST_ACCOUNT_FACEBOOK=<connected-account-id>
OPENPOST_ACCOUNT_INSTAGRAM=<connected-account-id>
OPENPOST_ACCOUNT_TIKTOK=<connected-account-id>
OPENPOST_ACCOUNT_LINKEDIN=<connected-account-id>
```

Secret:

```text
OPENPOST_API_TOKEN=<workspace token>
```

Keep the recurring backend on Buffer until validation is complete.

## 7. Current SocialMarket schedule contract

The weekly target stays at **300** total publications; LinkedIn was added by redistribution rather than by increasing volume:

| Channel | Weekly target | Automatic static formats |
|---|---:|---|
| Facebook | 110 | Feed/Post |
| Instagram | 90 | 72 Feed + 18 Story |
| TikTok | 70 | Photo Feed |
| LinkedIn | 30 | Feed/Post |

The executor can also handle Instagram Reel and TikTok video when a real approved video job is supplied. It does not convert a static PNG into a fake video.

## 8. Validate with zero mutations first

Manually dispatch **Social Scheduler**:

```text
publisher_backend = openpost
mode              = dry-run
content_source    = socialmarket_outbox
```

Dry-run performs no OpenPost writes and does not lease outbox rows.

After the workspace/account mappings and approved jobs are verified, perform one controlled live run. Only then consider changing the recurring `PUBLISHER_BACKEND` to `openpost`.

## Cost boundary

The OpenPost code and self-host mode do not require an OpenPost subscription. Potential costs are external to OpenPost and depend on choices you make, for example:

- a VPS/domain if you do not already have a suitable machine/hostname;
- provider-specific API policies or paid access where a social network itself requires it;
- optional third-party services that you explicitly configure.

For the architecture in this folder, OpenPost itself is the open-source execution service and does not require purchasing the Hosted plan.
