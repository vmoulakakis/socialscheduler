# Start here: free self-hosted OpenPost

1. Use a persistent Docker-capable machine.
2. Copy `.env.example` to `.env`.
3. Set a real public HTTPS `OPENPOST_APP_URL` before OAuth.
4. Generate new JWT/encryption secrets.
5. Run `docker compose up -d`.
6. Open the self-hosted UI, create the first account/workspace and connect Facebook / Instagram / TikTok.
7. Create a workspace API token and place it only in GitHub Secret `OPENPOST_API_TOKEN`.
8. Add the workspace/account IDs as GitHub repository variables.
9. Run Social Scheduler with `publisher_backend=openpost` and `mode=dry-run`.
10. Perform one controlled live validation before making OpenPost the recurring backend.

No OpenPost Hosted subscription is part of this path.
