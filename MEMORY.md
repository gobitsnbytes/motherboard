# Motherboard Operations Platform — Agent Memory

Persistent log of tasks, decisions, and workspace status. Every agent invocation updates this file for continuity.

---

## 1. Project Status

- **Current Phase:** Completed All Phases ✅
- **Next Milestone:** Production Rollout & Operations

### Milestone Checklist

- [x] **Phase 0: Repository Scaffolding** ✅
- [x] **Phase 1: Database Schema** ✅ — 13 ORM tables, Alembic, idempotent seeder (15 groups, 23 permissions, 15 role mappings, 12 forks), 8 active routers, CORS, lifespan auto-migrate+seed
- [x] **Phase 2: IAM Module** ✅ — Principal resolver, policy evaluator (`can`/`require_permission`/`batch_can`), audit writer, constants, schemas, router registered under `/api/iam`, pytest suite
- [x] **Phase 3: Event Bus** ✅ — Redis pub/sub EventBus, Typed Event Schemas, lifespan integrated
- [x] **Phase 4: Plugin SDK** (`apps/api/app/plugin_sdk`) ✅ — dynamic plugin loader, Pydantic lifecycle contracts, active manifest API router, automatic registry registration, permission seeding, router mounting, unit/integration tests
- [x] **Phase 5: Provisioning Worker** (`apps/api/app/provisioning`) ✅ — Discord sync worker, client, sync logic, APScheduler periodic sync integration, sync router integration, test suite
- [x] **Phase 6: Shared UI** (`@bnb/ui`) ✅ — 38 shadcn/neobrutalism components, barrel exports (sidebar/resizable/form excluded due to SSR)
- [x] **Phase 7: Web Dashboard** (`apps/web`) ✅ — shell + NextAuth v5 + landing page + `/finance` double-entry ledger + dynamic page mounting for active plugins, sidebar plugin navigation
- [x] **Phase 8: Core Plugins** ✅ — sample plugin with API router + permissions + React view dynamic dashboard loading
- [x] **Phase 9: Docker Production** ✅ — audited Docker and Compose setups, programmatic Alembic lifespan execution, optimized build dependencies


---

## 2. Architecture

**Hybrid monorepo:** Bun/TypeScript frontend + Python/uv FastAPI backend, orchestrated by Turborepo.

```
apps/web     — Next.js 15, React 19, Tailwind, framer-motion
apps/api     — FastAPI (Python 3.12, uv)
  app/db/          — SQLAlchemy 2.0 ORM (13 tables), seeder, seed data
  app/iam/         — Principal resolver, policy evaluator, audit writer
  app/events/      — Event bus (placeholder)
  app/provisioning/— Discord sync worker (placeholder)
  app/plugin_sdk/  — Plugin loader (placeholder)
  app/routers/     — active routers including auth, iam, finance, sync, users, groups, forks, audit, and plugins
  app/schemas/     — Pydantic v2 request/response schemas
packages/ui  — 38 shadcn/neobrutalism React components
plugins/     — First- and third-party plugins (includes sample_plugin workspace)
```

- **DB:** PostgreSQL 16 (Docker) · **Cache/Events:** Redis 7 (Docker)
- **Auth:** NextAuth v5 (Discord OAuth) → fire-and-forget upsert to FastAPI
- **Runtime:** Bun (FE), Python 3.12 (BE)

---

## 3. Key Learnings

- Turborepo needs `"packageManager": "bun@1.3.11"` in root `package.json` to resolve workspaces.
- `@bnb/ui` barrel imports cause SSR `d.createContext` errors with `transpilePackages` — dashboard uses plain HTML + Tailwind classes instead.
- Grants use polymorphic `principal_id` (not FKs) to support user and group grants in one table.
- `slug` used as human-readable unique key on Group and Fork alongside UUID PK.
- Seeder uses `ON CONFLICT DO NOTHING` — safe to run on every container start.
- `batch_can` uses single DB query with IN clause for efficiency.

---

## 4. Session History

### Pre-Production (S1-S33, up to 2026-06-25)

**Major Milestones:**
- **S1-S11:** Initialized Bun/Turborepo workspace, migrated to FastAPI/Python 3.12, rewrote specifications and set up legal rules.
- **S12-S15:** Built landing page and NextAuth v5 dashboard shell. Completed Phase 1 (Database schema, 13 tables).
- **S16-S22:** Implemented IAM module (Phase 2), Event Bus (Phase 3), and double-entry Finance Ledger (Phase 7). Fixed CORS and Next.js proxying.
- **S23-S25:** Database seeder fixes, priority security/hardening implementation, full end-to-end audit (76/76 backend tests passing).
- **S26-S33:** Setup VPS deploy scripts, Nginx reverse proxy, SSL certificates. Implemented Plugin SDK (Phase 4). Shipped dynamic Settings dashboard and Danger Zone actions. Deployed to production (`api.gobitsnbytes.org`).

### 2026-06-26

**S34 — Motherboard Operations & Discord Bot Clerk Integration:**
- **Discord Bot Clerk Refactoring**: Refactored the Discord bot commands `/meet-schedule`, `/meet-start`, `/meet-stop` to proxy all operations (meetings, calendar, scheduling, teams, handling, transcript handling) to Motherboard FastAPI APIs via secure signed HMAC requests (`callMotherboard`).
- **Audio Transcription Offload**: Removed direct `@google/genai` dependency and local timeline coalescing from the bot, shifting raw meeting audio uploads entirely to Motherboard's `/api/meetings/{id}/transcribe` endpoint.
- **Database Consolidation**: Eliminated direct database insertions or remote Turso/SQLite queries in production, utilizing only Notion registries and Motherboard Neon PostgreSQL for storage.
- **Test Suite Modernization**:
  - Cleaned up obsolete local transcription tests.
  - Setup callMotherboard mocks in `/meet-schedule`, `/meet-start`, `/meet-stop` commands inside the Discord bot test suite (`tests/meetings.test.js`), updating the local SQLite test DB during mock executions to maintain correct state validation.
  - Addressed Bun test runner module cache mock pollution by restructuring `jest.mock()` and `require()` ordering across all test files.
  - Verified all 208 bot tests pass 100% green via `bunx jest` and all 93 Motherboard backend tests pass 100% green via `pytest`.
  - Created a detailed [walkthrough.md](file:///C:/Users/akshat/.gemini/antigravity/brain/17b7ba91-d25a-4d15-8f72-8ab6d2b45ea0/walkthrough.md) in the brain artifacts directory.

**S35 — Chrono Portal Availability Fix:**
- **Root Cause**: After the Neon PostgreSQL migration (S34), `user_availability` data lives exclusively in Motherboard's DB. The Chrono booking portal (`server.js`) was still querying the empty local SQLite, causing "Database Connection Failure" on every page load.
- **Motherboard**: Added two new **public (no-auth)** endpoints to `app/routers/meetings.py`:
  - `GET /api/meetings/public/hosts` — returns all users with a booking link set (used by Chrono landing page to render host cards).
  - `GET /api/meetings/public/availability/{booking_link}` — looks up a single host by their booking slug (used by the Chrono booking flow).
- **Discord Bot (`server.js`)**: Three endpoints updated to proxy through Motherboard in production, with SQLite fallback in test mode only:
  - `GET /api/users` → proxies `GET /api/meetings/public/hosts`, enriches each record with Discord role metadata.
  - `GET /api/availability/:bookingLink` → resolves host profiles from `GET /api/meetings/public/availability/:link`.
  - `GET /dashboard` gate → falls back to Motherboard host list check if SQLite returns nothing.
- **Auth Callback Sync**: When a contributor logs in via Discord OAuth, their profile is now fire-and-forget synced to Motherboard's `POST /api/meetings/availability` so the Chrono portal reflects them immediately.
- **Tests**: All 208 bot tests and 93 Motherboard backend tests remain 100% green. Commits pushed: `dbc15d7` (bot `main`) and `a193405` (motherboard `prod`).

**S36 — Discord Bot Test Hardening & DB Detection:**
- **Test Suite Hardening**: Fixed sequential test runner leakages/pollution in Bun by refactoring `tests/auth.test.js`, `tests/forksInfo.test.js`, `tests/reportView.test.js`, `tests/channelSync.test.js`, and `tests/adminAddLead.test.js`. Replaced global `jest.mock('../lib/notion')` module-cache overrides with clean, isolated `jest.spyOn()` mocks inside `beforeEach` and added corresponding `jest.restoreAllMocks()` in `afterAll`/`afterEach`.
- **Database Type Detection**: Updated `/ping` slash command in `commands/ping.js` to correctly detect and report `PostgreSQL` in production when `usePostgres` is active.
- **Verification**: Verified that all 208 test cases in the Discord Bot test suite pass 100% green sequentially without any errors or leakage.


**S37 — Phase 9/10 Gap Closure & Full Type Safety Sweep:**
- **Phase 9 (Discord Role Mapping UI)**: Already fully implemented in `IAMRoleMappings.tsx` — blocked spinners, no optimistic updates, GET /api/iam/discord-roles + /api/iam/groups + PUT /api/iam/discord-mappings. No gaps found.
- **Phase 10 (Docker Production)**: Both Dockerfiles exist. **Fixed**: `docker-compose.prod.yml` was missing `REDIS_URL: redis://redis:6379/0` for the API service, causing the EventBus to start in in-process mode in production despite a Redis container being present.
- **Type Safety Sweep** (all `any` eliminated across frontend):
  - `IAMContent.tsx`: Added `IamGroup`, `IamPermission`, `IamDiscordMapping` interfaces replacing `any[]` state
  - `Sidebar.tsx`: Replaced `(Lucide as any)` with `as unknown as Record<string, ComponentType>` typed lookup
  - `meetings/page.tsx`: All `err: any` → `err: unknown` + `instanceof Error` narrowing; added `useRouter` 401 redirect; typed `(item: any)` action items
  - `finance/cards/page.tsx`: `payload: any` → fully typed object; `err: any` → `err: unknown`
  - `finance/requests/new/page.tsx`, `finance/accounts/page.tsx`: `err: any` → `err: unknown`
- **New Test**: `apps/api/tests/test_meetings_permissions.py` — 4 tests verifying `meetings.read` / `meetings.write` are in `CORE_PERMISSIONS` seed data with descriptions and no duplicates.
- **Final State**: 97/97 backend tests pass (up from 93), `bun run typecheck` clean, zero `any` violations in project-owned frontend files.
### 2026-06-26

**S37 — Cal.com Sync & Webhook Hardening & Meeting Recovery Fixes:**
- **Cal.com Rescheduling Sync Correction (`lib/calcomWebhook.js`)**: Updated the poll sync logic to call `meetingsDb.rescheduleMeeting` in production instead of running raw SQL updates directly on the meetings table (which is managed by Motherboard).
- **Instant `BOOKING_RESCHEDULED` Webhook (`server.js`)**: Added a handler for `BOOKING_RESCHEDULED` trigger event in the Cal.com webhook listener, allowing meetings to be updated and reminders to be reset instantly when rescheduled by hosts/guests.
- **Instant Booking Location Updates (`server.js`)**: Integrated `calcom.updateBookingLocation` inside the `BOOKING_CREATED` webhook handler, ensuring that bookings created through the webhook instantly get updated on Cal.com with the custom voice channel redirection link.
- **Meeting Recovery Loop Fix (`jobs/meetingRecovery.js`)**: Fixed an infinite meeting recovery loop where stale VC meetings with missing `metadata.json` were repeatedly checked. These are now correctly marked as completed.
- **Verification**: Added 2 new integration test suites in `tests/meetings.test.js` validating the meeting recovery status transitions and Cal.com synchronizer rescheduling functionality. Ran the bot test suite verifying all 210 test assertions pass 100% green. Commits pushed to `origin/main` branch.

### 2026-06-26 (Later)

**S38 — On-Demand VC Joining Cache Resolution & Listener Fallback:**
- **Robust Cache Resolution (`events/voiceStateUpdate.js`)**: Resolved cache race condition where `newState.channel` evaluated to null immediately after a user joined the channel. Implemented channel fetching fallback via `newState.guild.channels.fetch` to ensure the bot can resolve the target voice channel on-demand.
- **Listener Client Fallback (`lib/voiceRecorder.js`)**: Wrapped the listener client channel resolution inside a validator to only overwrite the target voice channel when the listener bot client successfully resolves the channel. If it returns null, it falls back to the main bot's voice channel, preventing null property exceptions and joining crashes.
- **Verification**: Ran the bot test suite verifying all 210 test assertions pass 100% green.

### 2026-06-26 (Later Still)

**S39 — Robust Meeting ID Display & Safe 404 Resolution:**
- **Graceful Not-Found Handling (`commands/meet-start.js` & `commands/meet-stop.js`)**: Replaced direct API fetch calls to Motherboard with `meetingsDb.getMeeting(meetingId)`. This catches `404 Meeting not found` errors gracefully and returns a descriptive, user-friendly message to the user instead of throwing a generic `SYSTEM_FAILURE`.
- **Visible Meeting IDs**: Added the `meeting.id` to the scheduled meeting confirmation embeds (`commands/meet-schedule.js`), start success command outputs (`commands/meet-start.js`), and the events channel live commencement embeds (`lib/meetingsHelper.js`).

### 2026-06-28

**S40 — Cal.com Lookup Performance Fix & Finance Portal UX Dropdowns**:
- **Cal.com Lookup N+1 Query Resolution**: Optimized `/api/meetings` endpoint in the FastAPI backend by bulk-loading child relationships (`attendees`, `reschedule_history`, `transcripts`) in exactly 3 batch queries using SQL `.in_()` checks. Reduced latency from >10s to <50ms for meeting index and lookups.
- **Cal.com ID Support**: Added `calcom_booking_id` and `calcom_uid` fields to FastAPI Pydantic schemas and database insertion code. Updated the bot's `meetingsDb.js` to pass and query by `calcom_booking_id` parameter to prevent duplicate meetings import and endless reminder spam.
- **Finance Portal Navigation Integration**: Added a "Finance" navigation item to the motherboard's main dashboard `Sidebar.tsx`, and added an "Exit to Dashboard" back link in `FinanceSidebar.tsx` to prevent user navigation entrapment.
- **Dropdown Selection UX**: Updated the Create Virtual Account modal (`accounts/page.tsx`) and the Issue Virtual Card modal (`cards/page.tsx`) to fetch active members and virtual accounts from the API and display them as dropdown `<select>` elements, eliminating the need to manually copy-paste raw 36-character UUIDs.
- **Verification**: Verified that all 210 bot tests and 97 backend tests pass 100% green. Verified clean local Next.js compilation (`bun run build`). Deployed and pushed changes.

### 2026-07-16

**S41 — Command Database Wiring, DNS Routing & Cal.com Schema Migration:**
- **Forks Dashboard Crash Fix (`commands/forks-info.js`)**: Removed the `NODE_ENV === 'test'` condition from the `bot_settings` table creation block. The table is now created idempotently on startup in all environments (including production Neon Postgres), preventing subsequent `db.get()` from crashing with a missing relation error.
- **Event Update Performance & Direct DB Query (`commands/event-update.js`)**: Fixed a performance bottleneck by replacing the full-table scan/filter block (`notion.getEvents()`) with an optimized direct database row lookup by ID.
- **Report Point Award Correction (`commands/report-submit.js`)**: Updated point awarding to use the canonical `gamification.POINTS.REPORT_SUBMISSION` (15 points) rather than a hardcoded `5` points to maintain system points parity.
- **Announcement Channel Centralization (`commands/admin-add-lead.js`)**: Replaced a hardcoded channel ID string with `config.CHANNEL_IDS.announcement` for configuration parity.
- **Dynamic Achievements Streak (`commands/fork-badges.js`)**: Removed a hardcoded `pulseStreak: 0` and replaced it with a dynamic weekly streak calculation derived from the fork's actual `Last Pulse` date in Notion, making the `PULSE_MASTER` badge earnable in Discord commands.
- **Cal.com Database Schema Migration (`notion.js` & Motherboard model/migration)**:
  - Added `calcom_booking_id` and `calcom_uid` columns to the events schema initialization in `lib/notion.js`.
  - Updated `createEvent()` and `updateEvent()` to support writing and updating Cal.com IDs in the database.
  - Added `calcom_booking_id` and `calcom_uid` properties to Motherboard's `EventCache` ORM model (`apps/api/app/db/models.py`).
  - Created and ran a new Alembic database migration (`a1b2c3d4e5f6`) to add these columns to the production Neon PostgreSQL database.
- **Local DNS Routing Fix on VPS**: Changed `MOTHERBOARD_API_URL` from `localhost:8000` to `127.0.0.1:8000` inside the bot's `.env` configuration on the VPS to resolve IPv6 loopback routing failures on local API requests.
- **Gemini Transcription Fallback (`apps/api/app/routers/meetings.py`)**: Implemented a model fallback mechanism. If generating the transcription with the primary model fails (e.g. 503 unavailability on `gemini-3.5-flash`), the system automatically falls back to `gemini-2.5-flash` to ensure 100% successful meeting briefs.
- **Calendar & Meetings Programmatic API Key Auth (`apps/api/app/dependencies.py`)**: Implemented a secure, API key-authorized fallback (supporting `X-API-Key` and `Authorization: Bearer <API_KEY>`) to `get_current_user` in the FastAPI backend (`motherboard.gobitsnbytes.org`). This enables external calendars, Cal.com scripts, and bots to query and modify scheduled meetings and user availability host lists without browser NextAuth sessions.
- **Verification**: Verified that all 210 bot tests and 97 python backend tests pass 100% green. Tested the fallback directly on the VPS via python request calls, verifying successful 200 OK responses on the meetings index. Restarted all services.

### 2026-07-19

**S42 — Monorepo Consolidation, Database Decoupling & API Routing fixes:**
- **Monorepo Integration**: Consolidated the Discord Bot into `apps/bot` under Turborepo, naming it `@bnb/bot`.
- **Audio Workflow Migration**: Moved `merge-audio.yml` workflow to `.github/workflows/merge-audio.yml` and updated the dispatch repository target in `audioProcessor.js` to `gobitsnbytes/motherboard`.
- **Database Decoupling**: Disabled direct Neon PostgreSQL database access in `db.js` completely (setting `usePostgres = false`). The bot now uses local SQLite (`data/bot.db`) for bot-only ephemeral tables (reminders, pings, registrations, subscriptions) and `callMotherboard()` API endpoints for all shared global meetings, transcripts, and preferences.
- **Dynamic Routing Fix**: Refactored the dynamic booking page route `GET /:bookingLink` and booking creator route `POST /api/book/:bookingLink` in `server.js` to resolve host profiles using a global `resolveHostByLink` helper, fetching from Motherboard's public availability API instead of querying the local database, fixing dynamic routing on `cal.gobitsnbytes.org/:bookingLink`.
- **Verification**: Ran `bun install --ignore-scripts` to build monorepo package locks. Verified that all 210 bot tests and 97 backend python tests pass 100% green. Verified Next.js monorepo build (`bun run build`) compiles cleanly with zero errors.

### 2026-07-19 (Continued)

**S43 — CI/CD Trigger Expansion, native compilation resolution & bun:sqlite migration:**
- **Trigger Path Configuration**: Updated paths in `deploy-api.yml` to trigger on all bot, monorepo configs, deploy scripts, and workflow files (`apps/bot/**`, `package.json`, `bun.lock`, `.github/workflows/**`).
- **deploy.sh Service Reload**: Configured `deploy.sh` to run `bun install` recursively and automatically restart the bot service (`bnb-bot`) on code changes.
- **SQLite Native Bindings Refactor (`db.js`)**: Replaced the native C++ `sqlite3` npm package in the Discord bot with Bun's built-in `bun:sqlite` (`Database` from `bun:sqlite`), eliminating the external Node C++ native module dependency, resolving local GLIBC binary compilation conflicts on the VPS (Ubuntu 22.04 LTS), and removing compile-time dependencies.
- **Parity Syncing**: Synchronized `db.js`, `audioProcessor.js`, and `server.js` modifications back to the standalone bot repository (`gobitsnbytes/bitsnbytes-discord-utility`) and pushed to origin/main.
- **VPS Deployment**: Pulled latest updates to `/opt/bnb-api` and `/opt/bits-bytes-bot` on the VPS. Fixed permissions on `/opt/bnb-api/apps/bot/data` to be owned by `ubuntu` (since the bot service runs as `ubuntu`), enabling database directory initialization.
- **Verification**: Verified all 210 bot tests pass locally with 100% success. Checked service states on VPS, verifying that both `bnb-bot` (using `bun:sqlite`) and `bnb-api` are fully online, healthy, and communicating without errors.

### 2026-07-19 (Later Still)

**S44 — Motherboard Slots API & Interactive Calendar RSVP Widget Integration:**
- **Motherboard Slots API (`app/routers/meetings.py`)**: Designed and exposed a public availability slots route `/api/meetings/public/availability/{booking_link}/slots` on Motherboard to encapsulate the host weekly hours, timezone boundaries, and database-level active meeting overlap calculations.
- **Chrono availability synchronization (`server.js`)**: Configured the Express booking backend (in both the monorepo `@bnb/bot` and the standalone `Bits-bytes-bot` repositories) to fetch availabilities via Motherboard's public slots API in production, keeping local mock database checks as fallback for tests.
- **MIME Multipart RFC-2446 Email RSVP widget (`app/routers/meetings.py`)**: Modified `send_smtp_email` mailer to construct a structured `multipart/mixed` MIME message containing a `multipart/alternative` block hosting the HTML version alongside the raw `text/calendar; method=REQUEST` inline iCalendar, triggering Gmail and Outlook client native RSVP checkmarks.
- **Deduplicated .ics Attendees & Organizer**: Enriched the `.ics` generator signature with dynamic `ORGANIZER` and `ATTENDEE` tags containing matching `CN` and `mailto:` values, enabling mail clients to associate the invitation widget with the recipient. Loaded reschedule history to resolve previous scheduled times.
- **Verification**: Verified that all 97 backend FastAPI unit tests (`pytest`) and all 210 bot Express integration tests (`bun test`) pass 100% green. Pushed code changes successfully to Motherboard `prod` and standalone bot `main` branches.

