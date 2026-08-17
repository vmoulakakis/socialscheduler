# OpenPost on Windows — zero OpenPost subscription

This is the recommended **zero-hosting-cost** runtime for the current SocialMarket / SocialScheduler setup when an always-on Windows PC is available.

It uses:

- the official `openpost-server-windows-amd64.exe` release;
- local SQLite + local media under `%LOCALAPPDATA%\OpenPost`;
- Tailscale Funnel for a public HTTPS `*.ts.net` endpoint;
- Windows Startup for automatic OpenPost restart after sign-in.

No OpenPost Hosted subscription is used.

## Why this path

Free cloud web services commonly sleep and/or use ephemeral disks. OpenPost needs durable OAuth credentials, scheduled jobs and media. Running the official Windows server binary locally keeps those durable without buying a VPS.

The PC must stay powered on and connected to the internet for scheduled publishing to work.

## One command

Open **PowerShell** and run from the SocialScheduler repository:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\deploy\openpost-windows\install-openpost.ps1
```

The installer:

1. creates `%LOCALAPPDATA%\OpenPost`;
2. downloads the latest official OpenPost Windows server from GitHub Releases;
3. verifies its GitHub-provided SHA-256 digest when available;
4. installs Tailscale with `winget` if needed;
5. performs the one-time Tailscale login if the machine is not connected yet;
6. derives the stable `https://<machine>.<tailnet>.ts.net` public URL;
7. generates unique OpenPost JWT and AES encryption secrets locally;
8. configures SQLite/local media;
9. starts OpenPost on `127.0.0.1:8080`;
10. enables Tailscale Funnel HTTPS to the local OpenPost service;
11. checks local and public health endpoints;
12. creates a desktop `OpenPost` shortcut;
13. configures OpenPost to start automatically when the user signs into Windows.

The generated secrets remain only under `%LOCALAPPDATA%\OpenPost\openpost.env.ps1` and must never be committed or pasted into chat/issues.

## One-time interactive steps

The installer can do the machine work, but identity grants must remain interactive:

1. Tailscale browser login, if Tailscale is not already authenticated.
2. Create the first local OpenPost account.
3. Configure the provider developer apps.
4. Connect Facebook / Instagram / TikTok / LinkedIn via their OAuth screens.
5. Create a workspace API token with `api:write`.

These steps intentionally cannot be automated with someone else's identity.

## Social provider callbacks

If the installer gives this example URL:

```text
https://my-pc.example-tailnet.ts.net
```

use these exact callback shapes in the provider developer portals:

```text
Facebook  https://my-pc.example-tailnet.ts.net/api/v1/accounts/facebook/callback
Instagram https://my-pc.example-tailnet.ts.net/api/v1/accounts/instagram/callback
TikTok    https://my-pc.example-tailnet.ts.net/api/v1/accounts/tiktok/callback
LinkedIn  https://my-pc.example-tailnet.ts.net/api/v1/accounts/linkedin/callback
```

The exact host comes from your own Tailscale account and is printed by the installer.

## After OAuth connection

Create a workspace API token inside OpenPost and configure SocialScheduler:

Secret:

```text
OPENPOST_API_TOKEN
```

Variables:

```text
OPENPOST_API_URL=https://<your-ts.net-host>/api/v1
OPENPOST_WORKSPACE_ID=<workspace id>
OPENPOST_ACCOUNT_FACEBOOK=<account id>
OPENPOST_ACCOUNT_INSTAGRAM=<account id>
OPENPOST_ACCOUNT_TIKTOK=<account id>
OPENPOST_ACCOUNT_LINKEDIN=<account id>
```

Keep `PUBLISHER_BACKEND=buffer` until an `openpost + dry-run` succeeds.

## Runtime locations

```text
%LOCALAPPDATA%\OpenPost\openpost-server.exe
%LOCALAPPDATA%\OpenPost\data\openpost.db
%LOCALAPPDATA%\OpenPost\data\media\
%LOCALAPPDATA%\OpenPost\logs\
%LOCALAPPDATA%\OpenPost\openpost.env.ps1
```

## Start / stop

After installation:

```powershell
powershell.exe -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\OpenPost\start-openpost.ps1"
powershell.exe -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\OpenPost\stop-openpost.ps1"
```

## Uninstall

Remove OpenPost and its data:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\deploy\openpost-windows\uninstall-openpost.ps1
```

Preserve SQLite/media while removing the runtime/startup entry:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\deploy\openpost-windows\uninstall-openpost.ps1 -KeepData
```

The uninstaller does not uninstall Tailscale.

## Important availability boundary

This is a zero-cost self-host, not a cloud SLA. If Windows sleeps, shuts down, loses internet, or Tailscale is disconnected, OpenPost is unavailable. Configure the PC to remain awake while plugged in if it will be the production publisher.
