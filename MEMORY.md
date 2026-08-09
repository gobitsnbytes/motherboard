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
- [x] **Phase 10: chrono ↔ Motherboard Meetings Unification** ✅ — seamless integration of all chrono features into the Motherboard meetings tab. See §6.
- [x] **Phase 11: Cockpit Architecture & UI Redesign** ✅ — Auto-login, fixed logout, Team Profile Setup (Chrono v2), Cockpit Debugger ("Stats for Nerds"), AI Agent Ops panel, Skeleton loaders, and Diagrammatic IAM Hierarchy visualizer. See §7.

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

### 2026-08-04

**S46 — Internal Contract Assistant & bnb-signatures Overhaul**:
- **Signature Canvas Overhaul (`SignatureCanvas.tsx`)**: Added Upload tab (for image files of wet signatures), 5 script font picker options for typed signatures, and draw canvas clear/pressure support.
- **Envelope Status Resolution & Contextual Signing Portal (`/sign/[token]/page.tsx` & `signatures.py`)**: Added `GET /api/signatures/sign/{token}/status` endpoint. Updated public signing page to poll envelope status after signing and render contextual state ("Fully Executed & Sealed" vs "Signature Recorded — Pending Remaining Signatories").
- **Email Security & Dispatch Formatting (`signatures.py`)**: Cleaned email HTML formatting, added List-Unsubscribe headers, direct non-tracked link fallbacks, and proper display names.
- **Inbound Email Domain Restriction (`contract_assistant.py`)**: Added strict `@gobitsnbytes.org` sender check (HTTP 401 on unauthorized domains) to `/api/contract-assistant/inbound-email` webhook.
- **Contract Assistant Database ORM Models (`models.py`)**: Added `ContractAssistantContract`, `ContractAssistantClause`, `ContractAssistantFinding`, `ContractAssistantSignatory`, `ContractAssistantEnvelope`, and `ContractAssistantEvent` ORM models.
- **Contract Dispatch & Search Endpoints (`contract_assistant.py`)**: Added `/dispatch` (with high-risk unresolved gate check) and `/ask` (RAG across OKF documents).
- **Kanban Pipeline Board (`dashboard/contract-assistant/page.tsx`)**: Rebuilt Contract Assistant landing page into a 3-column Kanban pipeline board (`In Review`, `Out for Signature`, `Dotted & Sealed`) with quick search and contract upload triggers.
- **OKF Rules Reference Panel (`dashboard/contract-assistant/rules/page.tsx`)**: Built read-only reference panel displaying 35 OKF policy rules with search and tag filters.
- **Contract Review & Triage Screen (`dashboard/contract-assistant/[contractId]/page.tsx`)**: Built 2-pane review layout featuring clause text viewer, findings list with source badges (`⚡ OKF Rule` vs `✨ AI Pass`), Tier-1/Tier-2 redline diff modal, per-clause chat, and sticky dispatch gate bottom bar.
- **Verification**: Verified `bun run typecheck` passes cleanly (code 0). Verified `pytest` passes 100% green across signature router tests and contract assistant test suites.

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

### 2026-08-02

**S45 — VPS Database Recovery & End-to-End Digital Signature System (`bnb-signatures`)**:
- **VPS Database Recovery**: Diagnosed `POST /api/auth/upsert` HTTP 500 errors on `bnb-backend`. Extracted `asyncpg.exceptions.InsufficientResourcesError` from journalctl logs caused by Neon Postgres compute quota limits. Deployed persistent Docker container `bnb-postgres` (`postgres:16-alpine`), updated `.env` configs, ran Alembic migrations (`alembic upgrade head`), and executed `run_seeds`. Restored `bnb-api` and `bnb-bot` service health (HTTP 200).
- **Backend Signature Engine (`app/services/signature_engine.py`)**: Implemented PyMuPDF 150 DPI base64 page preview generator, `.docx` to PDF converter (`python-docx` + `reportlab`), 1-page Audit Certificate generator, signature image overlay embedding, and SHA-256 tamper-evident checksum sealing.
- **ORM & Alembic DDL Migration (`f1a2b3c4d5e6`)**: Added `SignatureRequest`, `SignatureRecipient`, `SignatureField`, and `SignatureAuditLog` tables.
- **REST Router (`app/routers/signatures.py`)**: Exposed `/upload`, `/requests`, `/sign/{token}`, `/requests/{id}/download`, and `/verify/{id}` endpoints.
- **Pytest Suite (`tests/test_signatures_router.py`)**: Verified 103/103 tests pass 100% green across `apps/api`.
- **Frontend Signature Platform (`apps/web`)**:
  - `SignatureCanvas.tsx`: HTML5 canvas for drawing mouse/touch bezier curves or typing cursive script signatures.
  - `DocumentEditor.tsx`: Responsive PDF previewer with drag & drop field placement.
  - Overview Dashboard (`/dashboard/signatures`): Contract filter tabs, status badges, PDF download triggers, and verification links.
  - 4-Step Builder (`/dashboard/signatures/builder`): Document upload $\rightarrow$ Signatories $\rightarrow$ Visual canvas $\rightarrow$ Review & Dispatch.
  - Public Signing Portal (`/sign/[token]`): Tokenized recipient signing view with passcode security gate and legal consent agreement.
  - Public Verification Portal (`/verify/[documentId]`): Public authenticity check rendering SHA-256 checksums and audit trail timeline.
  - Navigation: Linked `Signatures` to `Sidebar.tsx`.


**S46 — chrono ↔ Motherboard Meetings Unification (Phase 10)**:
- **Problem**: Two parallel systems — `chrono` (bot/public/*.html Express portal) and `apps/web/app/dashboard/meetings/page.tsx` — sharing the same FastAPI `/api/meetings/` backend but feeling like completely separate apps. Critical data contract mismatch: `weekly_hours` was stored as structured JSON by chrono but free-text string by motherboard.
- **New components (apps/web/components/dashboard/)**:
  - `AvailabilityGrid.tsx` — Interactive 7-day availability grid with toggle switches, multi-slot-per-day support, "copy to all" UX. Reads/writes same JSON format as chrono's `dashboard.html` (`{"monday": [{"start": "09:00", "end": "17:00"}], ...}`). Includes preset buttons (Weekdays/Weekend/All/Clear).
  - `ChronoHostGrid.tsx` — Host discovery card grid, fetches from public `/api/meetings/public/hosts` endpoint. No auth required. Shows avatar, title, timezone. Click to select.
  - `ChronoBookingPanel.tsx` — Full booking flow: duration selector, month calendar, slot list from `/api/meetings/public/availability/{link}/slots`, booking form (title/notes/scope), submits to authenticated `/api/meetings/schedule`.
- **Meetings page (`apps/web/app/dashboard/meetings/page.tsx`) full rewrite**:
  - ⚡ Instant Meet launcher (always visible at top, same scope options as chrono index.html including tech/creative/ops councils)
  - **"Book a Sync" tab**: integrates `ChronoHostGrid` + `ChronoBookingPanel` inside the dashboard — no need to visit `cal.gobitsnbytes.org` for internal bookings.
  - **"My Availability" tab**: now uses `AvailabilityGrid` component instead of free-text. Booking handle slug editor with `cal.gobitsnbytes.org/` prefix preview.
  - **Meetings list**: "Join VC" button for active meetings, external meeting page deep-link (`cal.gobitsnbytes.org/m/{code}`) on every card.
  - **Reschedule modal**: inline form fires `PATCH /api/meetings/{id}`.
  - **Detail modal**: action bar with Join VC + Open Meeting Page + Reschedule + Cancel, full transcript with search.
- **TypeScript**: all 3 new files pass strict typecheck (0 errors).
- **Data contract**: `weekly_hours` is now always serialized as JSON object — `AvailabilityGrid` handles both empty/null and legacy object. Both surfaces write the same format.

### 2026-08-04 (Later)

**S47 — Meetings Dashboard UI & Responsive Layout Overhaul**:
- **Problem**: In the Meetings dashboard, selecting "My Availability" or "Notifications" rendered single-column forms constrained to `max-w-2xl` and `max-w-lg` aligned to the left half of the page, leaving a massive empty black void across the right half of wide screens.
- **Full-Width Responsive Layout (`apps/web/app/dashboard/meetings/page.tsx`)**:
  - Expanded wrapper max-width to `max-w-7xl` with responsive container padding (`p-4 sm:p-6 lg:p-8`).
  - **My Availability Tab**: Refactored from narrow single column into a full-width 2-column grid (`grid grid-cols-1 lg:grid-cols-12 gap-6`).
    - *Left Column (`lg:col-span-5`)*: Profile details (Email, Timezone, Title, Booking Handle, Short Bio, Cal.com Event Type ID) + **Live Guest Preview Card** showing how the host card renders to visitors on `cal.gobitsnbytes.org/{handle}`.
    - *Right Column (`lg:col-span-7`)*: `AvailabilityGrid` schedule editor with preset chips, day toggles, multi-slot pickers, copy-to-all controls, Web Push & Discord DM notification notes, and full-width green "Save Availability Settings" CTA.
  - **My Meetings Tab**: Added status filter chips ("All", "Scheduled", "Active", "Completed", "Cancelled"), meeting search bar, active meeting count badges, and responsive 3-column card grid (`grid-cols-1 md:grid-cols-2 lg:grid-cols-3`).
  - **Notification Preferences Tab**: Refactored into a balanced 2-column layout (`lg:col-span-7` settings card + `lg:col-span-5` integrations info card).
- **Verification**: Ran `npx tsc --noEmit` cleanly with zero TypeScript errors.

**S48 — Dyslexic UI, Root Route Aliases & Ground-Truth City Forks Cleanup**:
- **Dyslexic Root Redirect (`apps/web/app/dyslexic/page.tsx`)**: Created `/app/dyslexic/page.tsx` with server-side auto-redirect to `/dashboard/dyslexic` so navigating directly to `/dyslexic` in the browser URL resolves without a `404 Not Found`.
- **Top Header Quick Button (`apps/web/components/dashboard/Topbar.tsx`)**: Added a 1-click Dyslexic access button with a live pulse indicator to the top bar header.
- **Overview Dashboard Card (`apps/web/components/dashboard/OverviewContent.tsx`)**: Added a dedicated Dyslexic StatCard on the main overview dashboard linking to `/dashboard/dyslexic`. Updated `lib/dashboard.ts` to fetch live Dyslexic metrics via `/api/dyslexic/stats`.
- **Root Router Handlers (`apps/api/app/routers/dyslexic.py`)**: Added `@router.get("")` and `@router.get("/")` root endpoints on `APIRouter(prefix="/api/dyslexic")` to return dashboard stats and prevent direct GET `404` errors.
- **Ground-Truth Seeding Cleanup (`apps/api/app/db/seed.py`)**: Updated `seed_city_forks` to purge non-ground-truth fake/legacy forks and enforced real Notion ground-truth city forks (Lucknow HQ, Noida, Kolkata) and real team profiles in `run_seeds`.
### 2026-08-05

**S49 — Signature Email OTP, Class 1/2/3 DSC Support & IT Act Legal Page (`bnb-signatures`)**:
- **Unauthenticated Public Signing Access**: Updated `apps/web/app/api/[...path]/route.ts` to permit unauthenticated proxy access to `/api/signatures/sign/*` and `/api/signatures/verify/*` so external signatories can sign without NextAuth sessions.
- **6-Digit Email OTP Security Engine**: Added 2-stage verification flow (`POST /api/signatures/sign/{token}/request-otp` and `POST /api/signatures/sign/{token}/verify-otp`) with masked email challenge (e.g. `ak*******@g****.com`), 2-minute expiration countdown timer, background SMTP email dispatching, and per-recipient toggle in contract builder (`/dashboard/signatures/builder`).
- **Class 1, 2, 3 Digital Signature Certificate (DSC) Engine**:
  - Added `dsc_type`, `dsc_issuer`, `dsc_serial`, `dsc_common_name`, `allowed_sig_type` columns to `SignatureRecipient` model and Alembic migration `e5f6a1b2c3d4`.
  - Added endpoints `/api/signatures/sign/{token}/dsc-digest`, `/api/signatures/sign/{token}/dsc-hardware-seal` (for USB dongles ePass2003, HYP2003, eMudhra, NIC, VSign), and `/api/signatures/sign/{token}/dsc-pfx-seal` (for `.pfx` / `.p12` certificates via Python `cryptography.x509` and `pkcs12`).
  - Added dedicated **"DSC (Class 1/2/3)"** tab inside `SignatureCanvas.tsx` for hardware USB tokens and software certificates.
- **Statutory Legal Validity Page & Modal**:
  - Rendered a statutory legal framework modal and bottom footer cards on `/sign/[token]` referencing `d:/bitsnbytes/agreements/legal-docs/trust-center/terms-of-service.txt`:
    - Operating Entity: GOBITSNBYTES FOUNDATION (Section 8 Non-Profit Company under Companies Act 2013, Uttar Pradesh, India).
    - Section 10A of the IT Act, 2000: Enforceability of electronic contracts and e-signatures in Indian courts.
    - Section 65B of the Indian Evidence Act / BSA 2023: Primary electronic evidence admissibility for SHA-256 document checksums, execution timestamps, IP addresses, and email OTP logs.
    - DPDP Act 2023 & POCSO minor safeguarding compliance.
    - Cryptographic SHA-256 tamper-evident sealing.
- **Flexible Recipient Security Modes**: Added `allowed_sig_type` dropdown in `/dashboard/signatures/builder` per recipient: `"any"` (Default: DSC if available, or Simple OTP), `"dsc_only"`, and `"email_only"`.
- **Verification**: `bun run typecheck` passed cleanly (exit code 0 across `apps/web`), 4/4 signature backend tests passed 100% green via `pytest`. Fixed Alembic branching migration tree multiple heads error (`a7f3c92b1d84` chained after `e5f6a1b2c3d4`). Pushed commits `8d2fd4a` and `a03583f` to `origin/prod`.

**S50 — Database-Backed Contract Assistant & bnb-signatures Integration**:
- **Database Persistence**: Updated `POST /api/contract-assistant/analyze` to extract real PDF text (PyMuPDF `fitz`), execute OKF deterministic rules & SparkCloud AI risk passes, and persist `ContractAssistantContract`, `ContractAssistantClause`, `ContractAssistantFinding`, and `ContractAssistantEvent` directly into database tables.
- **Auto-Sync & Ingestion Engine (`_sync_signature_request_to_ca_contract`)**: Automatically ingests any unlinked `SignatureRequest` into `ContractAssistantContract`, running rule evaluations, generating risk findings, and rendering interactive legal overviews (`/dashboard/contract-assistant/[contractId]`).
- **Resilient Pipeline Normalization**: Normalized status strings across backend and frontend (`pending`, `out_for_signature`, `dotted`, `voided`). Added fallback array handling so 100% of pipeline contracts display cleanly on the Kanban board.
- **Vercel Build Fix**: Updated `PipelineContract` interface `status` type annotation in Next.js frontend, fixing Vercel deployment builds.

**S51 — Agreement Quash / Void, Client-Side Export Purge & Legal Copy Polish**:
- **Quash / Void Engine (`POST /api/contract-assistant/contracts/{id}/void`)**: Officially quashes and voids any agreement. Revokes all active recipient signing links and logs an immutable `VOIDED` audit log entry. Public signing/certificate portals state that execution was quashed by the issuing authority.
- **Client-Side Export & Complete Data Purge (`DELETE /api/contract-assistant/contracts/{id}` & `GET /api/contract-assistant/contracts/{id}/export-void`)**: Generates an immediate client-side text download of an official **Certificate of Cancellation & Voided Copy** (with SHA-256 checksum, timestamps, registered parties, and statutory IT Act 2000 Sec 10A / BSA 65B notices), followed by a complete database deletion of all associated contract and signature records.
- **Legal Copy Polish & UI Hardening**: Audited and polished `SigningPortalClient.tsx`, `verify/[documentId]`, and dashboard view pages to remove casual tone/placeholders and replace raw `alert()` popups with inline error banners.
- **Verification**: `bun run --cwd apps/web build` passed cleanly with Next.js 15, and pytest suite passed 6/6 tests (100% green). Pushed to `origin/prod`.
**S52 — Cockpit Architecture & UI Redesign (Auto-Login, Team Setup Profile, 2-Way Sync & Diagrammatic IAM Visualizer)**:
- **Auto-Login & Fixed Logout**:
  - Middleware (`apps/web/middleware.ts`) & Login Form (`apps/web/app/(public)/login/page.tsx`) auto-redirect authenticated sessions directly to `/dashboard/overview`.
  - Topbar (`apps/web/components/dashboard/Topbar.tsx`) updated to perform clean `signOut({ callbackUrl: "/login", redirect: true })` without leaving stale tokens.
- **Hero Section Redesign (`/impeccable quiet & distill`)**:
  - Refined `HeroSection.tsx` with ambient glass visual styling, balanced typography (`text-wrap: balance`), and direct "Enter Cockpit →" auto-detect action button.
- **Stats for Nerds & Debugger (`CockpitDebugger.tsx`)**:
  - Added dockable debug bar (`Ctrl+Shift+D`) displaying real-time API latency (ms), active user ID, Granted IAM Scopes, DB & WS status, and AI Token metrics.
- **Deep Agentic (AI Agent) Ops (`AgentOpsDrawer.tsx`)**:
  - Added live AI Agent control drawer for monitoring subagents (Contract Assistant, Notion Sync, Dyslexic Sourcing, Chrono v2 Scheduler), execution logs, and prompt execution.
- **Team Setup Profile (Chrono v2 Ready)**:
  - Added `GET /api/users/me` and `PATCH /api/users/me` endpoints in FastAPI backend (`apps/api/app/routers/users.py`).
  - Added single-source profile setup interface at `/dashboard/profile` (`ProfileContent.tsx`) for setting up Display Name, Bio, Role, Timezone, Skills, and Chrono v2 availability & call preferences.
- **Diagrammatic IAM Hierarchy & 2-Way Discord Sync**:
  - Added `GET /api/iam/hierarchy` endpoint in backend (`apps/api/app/routers/iam.py`).
  - Added interactive visual node tree (`IAMHierarchyVisualizer.tsx`) at `/dashboard/iam` mapping system levels (`Super Admin -> Executive -> Lead -> Member -> Bot`), linked Discord roles, and permission policies.
- **Skeleton Loaders**: Created `Skeletons.tsx` with shimmer loading cards and layout placeholders for Overview, IAM, Profile, and tables.
- **Verification**: `bun run typecheck` passed 100% cleanly (0 errors), `bun run build` built Next.js 15 app successfully, and `uv run pytest` passed 188/188 backend tests (100% green).

### 2026-08-09

**S53 — Nextcloud Workspace Unification & Motherboard Deprecation**:
- **Primary Operational Workspace**: Nextcloud (`workspace.gobitsnbytes.org`) officially established as the central Section 8 builder network operating hub replacing Motherboard.
- **Suite Apps Active**:
  - `/drive` → Nextcloud Files (5TB External Storage + PostgreSQL 14)
  - `/meet` → Nextcloud Talk (HD Video Calls + Public Guest Access & Screen Share)
  - `/calendar` → Nextcloud Calendar (CalDAV + Email Invites via `workspace@gobitsnbytes.org`)
  - `/mail` → Nextcloud Webmail (IMAP/SMTP connected to India server `161.118.162.166`)
  - `/deck` → Nextcloud Deck (Kanban Boards for Hackathons & Dev Squads)
  - `/wiki` → Nextcloud Collectives (Team Wiki & Knowledge Base)
  - `/forms` → Nextcloud Forms (Signups & Surveys)
  - `/tasks` → Nextcloud Tasks
  - `/notes` → Nextcloud Notes
- **Automated Mail Provisioner Daemon**: Background daemon `/usr/local/bin/bnb_auto_mail_provisioner.py` running on VPS automatically provisions `@gobitsnbytes.org` mailboxes on India mail server `161.118.162.166` whenever a team member provides their Legal Full Name.
- **Identity & Discord Auth**: Discord OAuth enabled with 1-click login on `workspace.gobitsnbytes.org`.
- **Broken Icons & SVG Optimization**: Fixed SVG icon rendering by installing `php8.3-imagick` & `libmagickcore-6.q16-6-extra`, setting `www-data:www-data` ownership on data directory, clearing theming caches, and adding `include mime.types;` & `image/svg+xml svg;` in Nginx static location blocks.

**S54 — Complete White-Labeling & 5TB Google Drive Integration**:
- **Full White-Labeling**: Custom bits&bytes™ SVG logo and favicons deployed. Set `theming.name="bits&bytes™ Workspace"`, `theming.slogan="Getting ambitious teenagers to ship meaningful tech"`, `theming.color="#97192C"` (bits&bytes Core Burgundy). Injected CSS in `guest.css` hiding all Nextcloud footer credits and branding links.
- **Mail SSO & Auto-Login**: Enabled `mail` app SSO auto-login (`provision-default-account=1`, `auto-provision=1`, `sso-login=1`). Configured Dovecot Master User authentication on India server (`161.118.162.166`). User mailboxes open directly without email password prompts.
- **Google Drive 5TB Storage Mount**: Created Mount #1 `Google Drive (5TB)` in Nextcloud `files_external` linked to `admin` group. Installed Rclone + Fuse3 for high-speed 5TB storage streaming.
- **Digital Signatures Shortcut**: Added `/signatures` clean redirect shortcut in Nginx to `https://gobitsnbytes.org/dashboard/signatures` for legal IT Act Section 10A digital contract signing.




### Session S55 (2026-08-09) - Performance Supercharging & Group Hierarchy Realignment
- **PHP 8.3 FPM OPCache & JIT**: Enabled 512MB RAM OPCache (`opcache.enable=1`, `memory_consumption=512`), JIT tracing compiler (`opcache.jit=tracing`, 128MB buffer), and 2GB RAM limit. Reduced TTFB response latency to 27-40ms.
- **Nginx Dynamic SVG Icon Route Fix**: Fixed Nginx `/svg/` dynamic rewrite route (`location ^~ /svg/ { try_files $uri /index.php$request_uri; }`) and cleared theming icon cache.
- **Group Hierarchy Realignment**:
  - **`admin` + `volunteer`**: Sanjay Singh & Vijay Kushwaha (Board Directors), Akshat, Yash, Devaansh, Srishti, Legal.
  - **`volunteer`** (Staff): All Admins, City Leads, and Volunteers (Hridyansh, Samiksha, Shantanu, Adithya, Atharva Upadhyay).
  - **`builder` & `community`**: Reserved for external guests and hackathon participants.
