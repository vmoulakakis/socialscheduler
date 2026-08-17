# Direct Browser Publisher Prototype

Goal: bypass Buffer while keeping the existing Social Scheduler queue, dedupe and safety logic.

## Architecture

SocialMarket / RAG-ranked campaign -> platform-specific copy + media -> Direct Browser Publisher -> native social scheduler UI.

Targets:
- `meta`: Facebook + Instagram through Meta Business Suite
- `tiktok`: TikTok Studio web upload/scheduler
- `linkedin`: LinkedIn native composer/scheduler

Browserbase provides the cloud browser. Passwords are never stored in this repository. Authentication is performed manually once in Browserbase Live View and retained with a persistent Browserbase Context.

## Safety phases

### 1. Login only

Run the GitHub workflow `Direct Browser Publisher Prototype` with:
- action: `login`
- platform: `meta`, `tiktok`, or `linkedin`

The workflow creates a Browserbase session and prints:
- `live_view_url`
- `context_id`
- platform login URL

Open the Live View, log in yourself, complete MFA if requested, then close/end the Browserbase session. Save the returned context ID as the corresponding GitHub Actions secret:

- `BROWSERBASE_CONTEXT_META`
- `BROWSERBASE_CONTEXT_TIKTOK`
- `BROWSERBASE_CONTEXT_LINKEDIN`

Required Browserbase secrets:
- `BROWSERBASE_API_KEY`
- `BROWSERBASE_PROJECT_ID`

Never paste social passwords into GitHub, ChatGPT prompts or repo config.

### 2. Dry-run only

Run the same workflow with `action: dry-run`.

The automation may:
- open the native composer;
- fill caption and tracking URL;
- upload media when a repository/local runner file is provided;
- open a scheduling panel;
- capture a screenshot.

It MUST NOT click the final Publish/Schedule action. The Python core contains a hard guard and unit tests for this.

Review the uploaded screenshot artifact and Browserbase session recording to validate selectors and account routing.

### 3. Live mode

Do not enable live mode until every platform has passed account-specific dry-run validation. Live mode requires an explicit code path with `allow_live=True`; it is intentionally not exposed by the prototype workflow.

## Why persistent contexts

Use one Browserbase Context per site/account. It stores the browser user-data directory (cookies/local storage/auth state) so the scheduler does not repeatedly ask for passwords or MFA.

## Why UI recipes are data-driven

Social UIs change. `config/browser_recipes.json` holds candidate composer URLs, selectors and button labels. When an interface changes, update and test the recipe instead of rewriting the scheduling engine.

## Promotion integration after validation

Once all three login contexts and selectors are verified, the next integration is:

1. read the approved SocialMarket Top-N promotion queue;
2. resolve the exact tracking URL and creative;
3. create separate Facebook, Instagram, TikTok and LinkedIn copy;
4. choose the platform-native schedule time;
5. execute one platform at a time;
6. capture final post/scheduled-post URL and screenshot;
7. write execution state back to SocialMarket/Supabase;
8. never retry a post blindly if final state is uncertain.

Buffer stays available as fallback until direct browser publishing has passed several controlled runs.
