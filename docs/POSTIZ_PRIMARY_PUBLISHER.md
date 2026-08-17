# Postiz Primary Publisher

## Target architecture

```text
SocialMarket intelligence / approvals
            |
            v
     publish.outbox
            |
            v
     SocialScheduler
        /       \
   Postiz       Buffer
  PRIMARY      FALLBACK
```

SocialMarket remains the only content/ranking/approval brain. Postiz and Buffer are execution backends only.

## Why Postiz is not deployed to Vercel

Current Postiz self-hosting requires PostgreSQL, Redis, Temporal and persistent media storage. Use the official `gitroomhq/postiz-docker-compose` stack on a Docker-capable VM/container host. Vercel remains suitable for the SocialMarket web application, not for the full Postiz runtime.

## Postiz deployment baseline

Use the official Docker Compose repository and configure at minimum:

- `MAIN_URL`
- `FRONTEND_URL`
- `NEXT_PUBLIC_BACKEND_URL`
- `JWT_SECRET`
- `DATABASE_URL`
- `REDIS_URL`
- `TEMPORAL_ADDRESS`
- storage settings (local persistent volume or Cloudflare R2)
- provider credentials for the social networks you connect

For production, serve Postiz through HTTPS on a stable domain because social OAuth redirect URLs depend on that domain.

## Social accounts

Connect Facebook, Instagram and TikTok from the Postiz UI using their OAuth flows. This step is intentionally interactive and must be authorized by the owner of each social account.

After the channels are connected:

1. Open Postiz Settings > Developers > Public API.
2. Create/copy the API key.
3. Add it to this repository as GitHub Actions secret `POSTIZ_API_KEY`.
4. Set repository variable `POSTIZ_API_URL` to the self-hosted `/public/v1` API base, or keep `https://api.postiz.com/public/v1` for Postiz Cloud.
5. If exactly one enabled Facebook/Instagram/TikTok integration exists, SocialScheduler auto-discovers its integration ID.
6. If multiple accounts exist for a platform, set `POSTIZ_INTEGRATION_FACEBOOK`, `POSTIZ_INTEGRATION_INSTAGRAM`, and/or `POSTIZ_INTEGRATION_TIKTOK` explicitly.
7. Run the Social Scheduler workflow in `dry-run` with `publisher_backend=postiz`.
8. When the dry-run is correct, set repository variable `PUBLISHER_BACKEND=postiz`.

## Safety properties

- The executor claims only SocialMarket `approved` outbox rows.
- Expired schedules are failed, never silently shifted to a later time.
- Postiz HTTP mutation requests are not automatically retried after ambiguous failures, preventing duplicate publishing.
- Media is copied into Postiz with `upload-from-url` before a post is scheduled.
- Successful Postiz post IDs are acknowledged back to SocialMarket.
- When Postiz credentials/integrations are unavailable, no jobs are claimed for those platforms.
- Buffer remains a rollback backend by setting `PUBLISHER_BACKEND=buffer`.

## Migration behavior

Already-scheduled Buffer posts remain in Buffer and can complete normally. Because those jobs are acknowledged in SocialMarket, Postiz will not claim them again. New approved outbox jobs move through the selected backend only.
