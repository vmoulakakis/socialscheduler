# SOCIAL MEDIA AUTOPILOT — MASTER SOURCE

**Project window:** August 2026 → November 2026  
**Primary timezone:** Europe/Athens  
**Buffer organization:** My Organization  
**Owner/account:** vmoulakakis@gmail.com

## 1. PROJECT GOAL

Build and operate a hands-off social-media engine across the user's active projects/sites. The system must create/maintain content, use supplied/generated graphics, schedule automatically through Buffer, and monitor the Buffer queue so the 10-scheduled-post limit never blocks publishing.

The user does **not** want daily manual work and wants the assistant to execute, monitor and recover automatically whenever safe. The intended operating model is:

**site/product → content concept → graphic/reel/story asset → caption/CTA → Buffer backlog → rolling 10-slot active queue → automatic publish → monitoring → refill queue → performance review**

## 2. BRAND / SITE SOURCES

### CoffeeGo AI
- URL: https://coffeego-ai.vmoulakakis.chatgpt.site/
- Positioning: AI guide for portable espresso / coffee setup selection.
- Core CTA: Smart Match / ask Elena / cost calculator.
- Content pillars: portable espresso education, setup comparison, coffee economics, Elena AI advisor, use cases, honest buying guidance.

### CabinPilot Travel
- URL: https://cabinpilot-travel.vmoulakakis.chatgpt.site/
- Positioning: cabin luggage / airline-rule / bag-fit decision support.
- Core CTA: check cabin fit before travel.
- Content pillars: airline rules, luggage dimensions, packing, fee avoidance, stress reduction, business-travel use cases.

### Λύσεις που Αξίζουν
- URL: https://lyseis-pou-axizoun.vmoulakakis.chatgpt.site/
- Positioning: practical/value solutions and useful tools/offers; avoid hype.
- Content pillars: “αξίζει / δεν αξίζει”, practical savings, business/e-commerce tools, pain-point solving.
- Current supplied creatives include BOX NOW / Biz Box Solver material that can be used in this brand stream where appropriate.

### Travel AI
- URL: https://travel-ai-navy-eight.vercel.app/
- Positioning: Greek AI travel discovery/advisor.
- Content pillars: destination discovery, seasonal Greece, weekend escapes, late summer, autumn trips, travel psychology/preferences, packages/ideas.

### CabinPilot Smart Savings
- Distinct campaign stream for crew/pilot travel savings and benefit/value content.
- Use only verified destinations/claims; some supplied creatives contain older URLs, so canonical destination must be checked before posting.

### Red Raven Eyewear
- URL: https://red-raven-eyewear-handcrafted-sunglasses-122630476133.europe-west1.run.app/
- Positioning: eyewear / sunglasses brand stream to be integrated into the same social portfolio.
- Safety rule: verify official Red Raven product, price, stock, warranty, UV/polarized, material and promotion claims before publication. Never present generic stock eyewear as a specific Red Raven model.

## 3. BUFFER CONNECTION — CURRENT SOURCE OF TRUTH

### Account
- Timezone: Europe/Athens
- Organization: `My Organization`
- Organization ID: `68a86463018d512de98d6315`

### Plan limits
- Channels: 3
- Scheduled posts: **10**
- Ideas: 100
- Tags: 3

### Connected channels
1. Facebook Page — **Sales for All**
   - Channel ID: `6a7c1fa2b2d9d57743615a1c`
2. TikTok — **billmtiktoker_ai**
   - Channel ID: `6a7c20eab2d9d57743615efa`
3. Instagram Business — **vassilis1969**
   - Channel ID: `68a864cf8e37dc1a589afa8b`

### Important channel constraint
There are only 3 Buffer channels. All four brands currently share these social accounts unless the user later reconnects/rebrands/adds channels.

## 4. ROLLING QUEUE STRATEGY

Because Buffer allows only **10 simultaneous scheduled posts**, never schedule the entire Aug-Nov calendar at once.

Use a two-layer architecture:

### Layer A — Master Backlog
Store all planned content as Buffer Ideas or drafts with:
- brand
- exact target date/time
- target service(s)
- caption/script
- CTA
- attached asset
- format (post / story / reel / TikTok)

### Layer B — Active Queue
Keep only the **next 10 eligible executions** in `scheduled` state.

Monitoring logic:
1. Check scheduled count.
2. If <10, fetch next dated backlog items in chronological order.
3. Verify attached media is valid for the target platform.
4. Schedule automatically at the planned time.
5. Stop when queue reaches 10.
6. Re-run monitoring hourly.
7. Never duplicate a content item already scheduled or sent.
8. If an item’s planned time has passed, move it to the next appropriate channel slot rather than publishing blindly.
9. Rotate brands so one brand does not monopolize the queue.

## 5. CURRENT BUFFER STATE AT SAVE TIME

The eight long-range CoffeeGo Facebook scheduled posts were intentionally moved to **draft** so they no longer consume the 10-slot queue. They were not deleted.

The latest checked active queue contained two CoffeeGo posts scheduled for **2026-09-02 18:30 Europe/Athens**:
- Instagram CoffeeGo portable espresso post
- TikTok CoffeeGo portable espresso post

### CoffeeGo Facebook drafts preserved
Original dates/topics retained as drafts:
- 01 Sep — “best portable espresso?”
- 04 Sep — bar myth
- 08 Sep — coffee cost calculator
- 11 Sep — office use case
- 15 Sep — capsule vs ground
- 18 Sep — Elena AI guide
- 22 Sep — when not to buy
- 25 Sep — Smart Match conversion

## 6. BUFFER IDEAS CREATED IN THIS PROJECT SESSION

These were created with the user-supplied PNG attached to the Idea record:

1. **CABINPILOT | 18 AUG | PACKING SMART**
   - Target: 2026-08-18 18:30 Europe/Athens
   - Services: IG / FB / TikTok
   - Asset: `1f5b50bf-1d60-43cc-9c2e-c6fb887f3625.png`
   - Idea ID: `6a7f01a34947a1e22e1e4ccf`

2. **CABINPILOT | 20 AUG | AIRLINE RULES**
   - Target: 2026-08-20 19:00
   - Services: IG / FB / TikTok
   - Asset: `67e3faee-e0dd-42e8-98ba-d41a18e7a4f7 (1).png`
   - Idea ID: `6a7f030d4947a1e22e1e57fe`

3. **CABINPILOT | 22 AUG | FIT CHECK**
   - Target: 2026-08-22 11:00
   - Services: IG / FB / TikTok
   - Asset: `4a2dbd9d-8491-4549-8487-568564c14273.png`
   - Idea ID: `6a7f0319ec11091f0416dd67`

4. **CABINPILOT SMART SAVINGS | 24 AUG | CREW BENEFITS**
   - Target: 2026-08-24 19:30
   - Services: IG / FB / TikTok
   - Asset: `1e7ab9f4-aeee-48c1-845a-1216c6cacd18.png`
   - Idea ID: `6a7f03249b401a4ea3e79499`

5. **CABINPILOT SMART SAVINGS | 26 AUG | CREW SAVINGS**
   - Target: 2026-08-26 18:30
   - Services: IG / FB / TikTok
   - Asset: `d98d229f-cfbf-4db1-b5bf-56a4e5458946.png`
   - Idea ID: `6a7f0330a6c8fc76f2b4c57c`

6. **BIZ BOX SOLVER | 28 AUG | SAVE THIS SITE**
   - Target: 2026-08-28 12:30
   - Services: IG / FB / TikTok
   - Asset: `8cd89403-c4ab-44de-abd8-3ecf73669725.png`
   - Idea ID: `6a7f033bec11091f0416ddd3`

7. **BIZ BOX SOLVER | 31 AUG | ESHOP SAVINGS**
   - Target: 2026-08-31 19:00
   - Services: IG / FB / TikTok
   - Asset: `454db2a9-fd56-4f26-b9a4-fbcfd1a103d0.png`
   - Idea ID: `6a7f0348a6c8fc76f2b4c5e9`

8. **COFFEE ANYWHERE | 3 SEP | WHICH SETUP**
   - Target: 2026-09-03 18:30
   - Services: IG / FB / TikTok
   - Asset: `dcbacef0-0c06-4ecc-b68a-2646a36e29ec.png`
   - Idea ID: `6a7f0356153244db8c91ee6f`

9. **COFFEE ANYWHERE | 6 SEP | ASK ELENA**
   - Target: 2026-09-06 10:30
   - Services: IG / FB / TikTok
   - Asset: `14757316-efeb-4e9a-a8a8-2ec610cbf3c9.png`
   - Idea ID: `6a7f0363a6c8fc76f2b4c6a4`

10. **COFFEE ANYWHERE | 9 SEP | LEARN BEFORE BUY**
    - Target: 2026-09-09 19:00
    - Services: IG / FB / TikTok
    - Asset: `b50b1fd0-6220-4d6a-ba77-33b1409f9e64.png`
    - Idea ID: `6a7f03709b401a4ea3e798d7`

11. **TRAVEL AI | 12 SEP | LAST MINUTE SUMMER**
    - Target: 2026-09-12 11:00
    - Services: IG / FB / TikTok
    - Asset: `8436efca-c596-4d76-98d6-3084889b9804.png`
    - Idea ID: `6a7f0383153244db8c91ef2a`

12. **TRAVEL AI | 16 SEP | ESCAPE IN 60 SEC**
    - Target: 2026-09-16 19:00
    - Services: IG / FB / TikTok
    - Asset: `b6f0b84a-80c1-4494-9bc1-8362b8017bed.png`
    - Idea ID: `6a7f03924947a1e22e1e5e0b`

The next Travel AI idea for 20 Sep was being prepared when the user asked to save the project. It has **not** been confirmed created yet.

## 7. USER-SUPPLIED CREATIVE ASSET INVENTORY

All of these should be preserved in the project Library assets folder and reused for Aug-Nov scheduling:

### CabinPilot Travel
- `1f5b50bf-1d60-43cc-9c2e-c6fb887f3625.png` — packing smart / QR / woman packing
- `67e3faee-e0dd-42e8-98ba-d41a18e7a4f7 (1).png` — airline rules / airport / woman
- `4a2dbd9d-8491-4549-8487-568564c14273.png` — cabin fit / airport / man
- `3e07ef87-e1fb-4a57-8a87-e56b6730ad5a.png` — business traveller / problem vs solution / cabin bag

### CabinPilot Smart Savings
- `1e7ab9f4-aeee-48c1-845a-1216c6cacd18.png` — TikTok concept board / crew benefits
- `d98d229f-cfbf-4db1-b5bf-56a4e5458946.png` — crew savings / app benefit calculator

### BOX NOW / Biz Box Solver
- `8cd89403-c4ab-44de-abd8-3ecf73669725.png` — “ένα site που αξίζει να κρατήσεις”
- `454db2a9-fd56-4f26-b9a4-fbcfd1a103d0.png` — e-shop savings / monthly calculation

### CoffeeGo / Coffee Anywhere AI
- `dcbacef0-0c06-4ecc-b68a-2646a36e29ec.png` — portable setup types comparison
- `14757316-efeb-4e9a-a8a8-2ec610cbf3c9.png` — Elena / 9 answers 1 match
- `b50b1fd0-6220-4d6a-ba77-33b1409f9e64.png` — learn before you buy / 7 lessons
- `ef4a94d9-7ac2-45f4-a4e2-6933dc89159f.png` — CoffeeGo “Κάθε καφές, καλύτερη μέρα” / QR
- `c5cb6176-0dba-4442-b662-662118a03203.png` — CoffeeGo “Ο καφές που σου ταιριάζει” / QR

### Travel AI / GreekVibes
- `8436efca-c596-4d76-98d6-3084889b9804.png` — last minute September 2026 Greece
- `49ef86da-87b4-44be-88c6-536533369519.png` — autumn Oct-Nov 2026 escapes
- `21d95afb-46a2-4a48-9631-c418e4a7d503.png` — Greece you want to live / offers
- `b6f0b84a-80c1-4494-9bc1-8362b8017bed.png` — next escape starts in 60 sec
- `a5282e3d-7e8a-40e4-bb09-735f37a71862.png` — Greece search / offers 2026

## 8. CONTENT FORMAT SYSTEM

Do not run static posts only.

### Instagram
- Reels for reach
- Stories for engagement / polls / reminders / links
- Carousels/feed for education/trust

### Facebook
- Reels
- Stories
- selected feed posts with longer context and link intent

### TikTok
- native short-form hooks
- photo posts where appropriate
- video/reel variants when source media can support motion

### Repurposing rule
One core idea may become 3–4 executions, but **copy and hook must be adapted per platform**. Do not paste identical captions everywhere.

## 9. AUTOPILOT / MONITORING — CURRENT STATE

Automation ID: `6a7eef2213788191a47af61434edf8bc`

Current title: **Social Portfolio Silent Monitor**

Current verified state on 2026-08-14: **disabled**. The hourly schedule remains attached, but it must not be re-enabled until the Buffer queue is reconciled against the early-publish incident described below.

The monitor prompt now covers:
- CoffeeGo AI
- CabinPilot Travel
- CabinPilot Smart Savings
- Lyseis pou Axizoun / Biz Box Solver
- Travel AI / GreekVibes
- Red Raven Eyewear

### Hard scheduling safety rules
- NEVER publish a future-dated backlog item early.
- NEVER use `shareNow` or `shareNext` for backlog/future campaign content.
- NEVER change an existing scheduled `dueAt` merely to fill the queue.
- NEVER convert a future target date to current time.
- Use `customScheduled` with the intended future local date/time in Europe/Athens.
- If a planned date is already past, choose a new sensible future date from seasonality/context instead of publishing immediately.
- Queue may remain below 10; correctness is more important than filling slots.
- Never duplicate a sent or scheduled item.
- Automatically repair safe technical failures without changing campaign timing.

### Known incident — 2026-08-14
Several future posts were accidentally moved to approximately the current time and published early by autopilot behavior. This is a known failure mode. Before any future auto-fill run, reconcile `scheduled` + `sent` + `draft` + `Ideas`, then preserve original target dates.

One lower-priority/repetitive CabinPilot Smart Savings Facebook execution for 26 Aug was deliberately moved to **draft**, not deleted, during queue rebalance.

A Travel AI Instagram execution for **12 Sep 2026, 11:00 Europe/Athens** was attempted from the saved Travel AI Idea using `customScheduled`; its live Buffer status must be verified before relying on it as scheduled.

### Silent monitoring policy
- If everything is normal: no notification.
- If a safe technical problem can be fixed automatically: fix it and remain silent.
- Only unresolved/actionable issues should surface to the user.
- The user expects `Χρειάζεται από εσένα: Τίποτα` unless a genuine blocker exists.

### Daily report request
The user requested a daily report containing what actually posted in the last 24h, failures, next 48h, queue usage /10, early metrics if available, and what is required from the user. A separate `Daily Social Report` automation was previously attempted but was **not created** because the active-task limit was reached at that time. Re-evaluate current automation capacity before creating it.

## 10. PLANNED CAMPAIGN PHASES AUG-NOV

### Late August
- CabinPilot launch/usefulness
- cabin-fit / airline rule education
- crew Smart Savings
- practical tools / Biz Box Solver

### September
- CoffeeGo awareness + product education + Elena
- Travel AI late-summer discovery
- CabinPilot practical travel checks
- Red Raven awareness/product-education content, only with verified official claims

### October
- Travel AI autumn escapes
- CoffeeGo cost/value + buying decisions
- CabinPilot autumn city-break travel / baggage rules
- “Λύσεις που Αξίζουν” practical/value content
- Red Raven lifestyle / eyewear education and verified product storytelling

### November
- conversion-heavy content
- winter/holiday travel prep
- Black Friday / deal-awareness only when factual and current
- gifting/value content
- Red Raven gifting/seasonal content only when offers/stock are verified
- retargeting of strongest-performing themes

## 11. IMPORTANT EXECUTION RULES

1. User wants the system **fully automatic**, not a reminder to manually post.
2. Use uploaded/generated brand creatives where possible rather than generic stock.
3. QR codes must point to the correct site/source.
4. Do not fabricate discounts, airline rules, prices, or availability. Fresh claims should be verified before posting.
5. Maintain brand separation; avoid mixing CoffeeGo, CabinPilot, CabinPilot Smart Savings, Travel AI, Lyseis/Biz Box Solver and Red Raven identities in one creative unless intentionally cross-promoting.
6. Do not let Facebook consume all 10 queue slots.
7. Keep Buffer Ideas as the durable master backlog.
8. Treat the 10 scheduled posts as a rolling cache, not the campaign database.
9. Monitor post errors and sent status.
10. Use Europe/Athens times.

## 12. RESTART PROMPT FOR A NEW CHAT

Use this exact instruction if continuing in a new conversation:

> Open the Library project **Social Media Autopilot Aug-Nov 2026** and read `social_media_autopilot_master_source.md`. Continue the saved multi-brand Buffer autopilot from this checkpoint. Do not redesign from scratch. FIRST reconcile current Buffer `scheduled`, `sent`, `draft` and `Ideas` because of the 2026-08-14 early-publish incident. Then verify the `Social Portfolio Silent Monitor` state and re-enable it only after the queue is safe. Continue Aug-Nov content for CoffeeGo AI, CabinPilot Travel, CabinPilot Smart Savings, Lyseis pou Axizoun/Biz Box Solver, Travel AI/GreekVibes and Red Raven Eyewear, preserving intended future dates and a maximum of 10 scheduled posts.

## 13. NEXT ACTIONS AFTER THIS SAVE

1. Reconcile Buffer `sent`, `scheduled`, `draft`, and `Ideas` after the 2026-08-14 early-publish incident.
2. Verify whether the attempted Travel AI 12 Sep Instagram schedule exists and has the intended `dueAt`.
3. Keep the 26 Aug CabinPilot Smart Savings Facebook item as draft unless it is deliberately rescheduled later.
4. Research/verify official Red Raven site facts and create the first Red Raven backlog assets/Ideas before scheduling any product claims.
5. Continue Travel AI backlog after 16 Sep, add remaining CoffeeGo creatives, and add the CabinPilot business-travel creative.
6. Build October and November backlog across all six campaign streams.
7. Re-enable `Social Portfolio Silent Monitor` only after safety reconciliation; never use early-publish queue filling.
8. Add a daily report automation when task capacity permits, without sacrificing critical production/recovery monitors unless explicitly appropriate.
9. Once sent posts accumulate, use Buffer metrics to adjust future hooks/timing and preserve winners.

## 14. AUTOMATION SNAPSHOT — 2026-08-14

Verified via automation state:
- `Supabase Recovery` — enabled
- `V18 Production Watch` — enabled
- `V15 Production Watch` — enabled
- `Social Portfolio Silent Monitor` — disabled
- `Travel AI Deploy Retry` — disabled
- Several older monitoring/reporting tasks are paused/disabled.

This snapshot is historical state only; always re-check live automation state before changing or reporting status.

## 15. PROJECT PERSISTENCE

Persistent Library project folder:
`/Projects/Social Media Autopilot Aug-Nov 2026`

Master source:
`/Projects/Social Media Autopilot Aug-Nov 2026/social_media_autopilot_master_source.md`

Assets folder:
`/Projects/Social Media Autopilot Aug-Nov 2026/assets`

The master source should be treated as the resumable project context, while dynamic states such as Buffer queue, metrics, publishing status and automation enabled/disabled state must always be verified live before execution.

---

**This file is the operational source of truth for resuming the social-media autopilot project.**
