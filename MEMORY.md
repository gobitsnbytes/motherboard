# Motherboard Operations Platform — Agent Memory

Persistent log of tasks, architectural decisions, workspace status, and audit findings. Every agent invocation maintains this document.

---

## 2026-09-09 — IAM Overhaul Discovery

- User identified IAM as the first critical area for the 100-person / 30-city rollout.
- Focused IAM tests currently pass (`12 passed`), but coverage misses production risks.
- Confirmed concrete issues: expired memberships are not filtered by principal resolution; API-key fallback binds requests to the first super-admin; grant payloads lack strict principal/permission validation; `batch_can` has ambiguous per-key semantics; several IAM mutations lack audit writes; group management is duplicated under `/api/iam/*` and `/api/groups/*`.
- Working authorization assumption: city/fork-scoped RBAC, aligned with `docs/techspec.md` scopes such as `fork:{city}` and `fork:{city}:{track}`. Users may belong to multiple cities; explicit HQ/executive roles may be global.
- Proposed IAM contract: one canonical `/api/iam` surface, active/non-expired principal resolution, explicit global vs scoped permissions, break-glass super-admin only, transactional audit for every mutation, and Discord sync that preserves manual memberships.

### IAM Foundation Slice

- Filtered expired memberships out of principal resolution.
- Constrained grant principal types and permission-key shape at the Pydantic boundary.
- Added grant reference validation and creation audit entries.
- Replaced API-key binding to the first super-admin with an explicit `API_SERVICE_USER_ID`; missing, invalid, nonexistent, or super-admin service identities fail closed.
- Added regression coverage for expired memberships, invalid grant permissions, and service-auth isolation.
- Verification: focused IAM/auth suite `17 passed`; full backend suite previously `100 passed` before the final service-identity tightening.

### IAM Mutation Boundary Slice

- Added strict permission and group input validation.
- Added existence/active-state checks for grant principals, group membership targets, and Discord mapping groups.
- Rejected membership expiry timestamps in the past.
- Added audit entries for permission creation, group creation, membership creation, grant creation, and Discord mapping upserts.
- Verification: focused IAM/auth suite `20 passed`; full backend suite `101 passed`.

### IAM Policy Batch Semantics

- Changed `batch_can` to return an independent result for every `(permission_key, resource_scope)` pair instead of collapsing different city scopes into one boolean.
- Updated the policy regression test to assert allow for `res_1` and deny for `res_2` under the same permission key.
- Verification: IAM policy suite `7 passed`.

### IAM Service Identity Failure Handling

- Inactive configured service users now return 401 instead of leaking a `ValueError` as a 500.
- Verification: API-key authentication suite `8 passed`.

### Phase Verification

- Production-oriented review found no diff-format errors or new unhandled policy paths in the committed IAM/auth slices.
- Final full backend verification after all current fixes: `103 passed`.
- Current working tree still contains pre-existing untracked runtime artifacts (`.vercel/`, `apps/api/data/`, `apps/api/repro_temp.db`, `apps/bot/`, `apps/web/.vercel/`, `opencode.json`) that have not been touched or staged.

### IAM Authentication Ambiguity

- Mixed API-key and internal-signature credentials are now rejected with a 400 instead of silently selecting the API-key path.
- Verification: API-key authentication suite `7 passed`.

### IAM Global-Scope Leak Fix

- Fixed `can(permission, None)` so a city/resource-scoped grant cannot satisfy a global permission check; only an explicit unscoped grant can do that.
- Added regression coverage for the scoped-grant-as-global case.
- Verification: IAM policy suite `7 passed`.


## 1. Project Status

- **Current Phase:** All Phases Completed ✅ (Phases 0–11)
- **Production URL:** `https://motherboard.gobitsnbytes.org` · **API:** `https://api.gobitsnbytes.org`
- **Workspace Hub:** `https://workspace.gobitsnbytes.org` (Nextcloud Suite)
- **Latest Test Baseline:** 247/247 pytest passing (100% green), Next.js 15 build clean (31/31 routes).

### Milestone Checklist

- [x] **Phase 0: Scaffolding** ✅ — Bun/Turborepo workspace + FastAPI (Python 3.12, uv) monorepo.
- [x] **Phase 1: DB Schema** ✅ — SQLAlchemy 2.0 ORM (13 tables), Alembic, idempotent seeder, 8 active routers, auto-migrate lifespan.
- [x] **Phase 2: IAM Module** ✅ — Principal resolver, policy evaluator (`can`/`require_permission`/`batch_can`), audit writer, Pydantic schemas, visual hierarchy tree.
- [x] **Phase 3: Event Bus** ✅ — Redis 7 pub/sub EventBus, typed schemas, graceful fallback.
- [x] **Phase 4: Plugin SDK** ✅ — Dynamic loader, Pydantic lifecycle contracts, active manifest API, permission seeding, route isolation.
- [x] **Phase 5: Provisioning Worker** ✅ — Discord sync worker, APScheduler periodic sync, REST sync routes.
- [x] **Phase 6: Shared UI (`@bnb/ui`)** ✅ — 38 Neobrutalism React components (barrel exports avoided for SSR safety).
- [x] **Phase 7: Web Dashboard (`apps/web`)** ✅ — Next.js 15 App Router, NextAuth v5 (Discord OAuth), double-entry finance ledger, dynamic plugin loader.
- [x] **Phase 8: Core Plugins** ✅ — `email_server`, `minecraft_server` with real telemetry & admin permission gates.
- [x] **Phase 9: Docker & Deployment** ✅ — Multi-stage Dockerfiles, Docker Compose, automated VPS deploy script (`deploy.sh`), Nginx reverse proxy, SSL.
- [x] **Phase 10: chrono ↔ Motherboard Unification** ✅ — Single meetings backend, `AvailabilityGrid`, `ChronoHostGrid`, `ChronoBookingPanel`, RFC-2446 email RSVP, agenda calendar tab.
- [x] **Phase 11: Cockpit Architecture & Neobrutalism Overhaul** ✅ — Swiss Neobrutalism design system (Anton/Inter/JetBrains Mono), Cockpit Debugger (`Ctrl+Shift+D`), Agent Ops Drawer, `bnb-signatures` digital contract engine, Dottr-style Legal Agent.

---

## 2. Architecture & Monorepo Layout

Hybrid monorepo managed via Turborepo (`"packageManager": "bun@1.3.11"`):

```
apps/
  web/          — Next.js 15 (React 19, Tailwind, Framer Motion, Neobrutalism UI)
  api/          — FastAPI backend (Python 3.12, uv, SQLAlchemy 2.0 async, Alembic)
    app/db/       — ORM models, Alembic migrations, idempotent seeders
    app/iam/      — Principal resolver, policy evaluator, audit logger
    app/events/   — Redis EventBus pub/sub
    app/provisioning/ — Discord sync worker & background scheduler
    app/plugin_sdk/  — Dynamic plugin loader & manifest validator
    app/routers/  — auth, iam, finance, sync, users, groups, forks, audit, meetings, signatures, contract_assistant, dyslexic, plugins
    app/services/ — signature_engine, legal_agent, razorpayx_adapter, llm_client
  bot/          — Discord Bot clerk (@bnb/bot, Bun, bun:sqlite, signed HMAC API client)
packages/
  ui/           — @bnb/ui (38 Neobrutalism components)
plugins/        — email_server, minecraft_server, sample_plugin
```

- **Databases:** PostgreSQL 16 (Alembic head: `a9c4e7f1b2d6`) · Redis 7 · Local `bot.db` (`bun:sqlite`, ephemeral bot tables only).
- **Auth:** NextAuth v5 (Discord OAuth) → fire-and-forget upsert to FastAPI `/api/auth/upsert`. Public signing/verification routes bypass NextAuth.
- **Mail & Relay:** Postfix/Dovecot on VPS + Brevo SMTP relay fallback (`smtp-relay.brevo.com:587`). Mandatory CC to `gobitsnbytes@gmail.com` across all systems.

---

## 3. Key Learnings & Engineering Gotchas

1. **Turborepo Workspace Resolution:** Root `package.json` must explicitly specify `"packageManager": "bun@1.3.11"`.
2. **SSR Barrel Import Safety:** `@bnb/ui` barrel imports cause `d.createContext` errors with Next.js `transpilePackages` — use direct component imports or Tailwind utility tokens.
3. **IAM Polymorphic Grants:** `grants` table uses polymorphic `principal_id` (not foreign keys) to unify user and group grants in a single table.
4. **FastAPI Plugin Route Cloning:** APIRouters resolve route dependencies lazily. To enforce plugin permissions without mutating source routers or causing accumulation across reloads, the loader mounts a shallow clone (`copy.copy`) of each `APIRoute` with injected IAM dependencies.
5. **aiosqlite / Pytest Event-Loop Isolation:** Shared SQLAlchemy engines across pytest-asyncio function-scoped loops cause connection leakage and rotating StaleDataErrors. Tests creating isolated transactions must use per-test `create_async_engine(..., poolclass=NullPool)` and explicitly dispose at teardown.
6. **Timezone Normalization (SQLite vs Postgres):** `DateTime(timezone=True)` reads back naive on `aiosqlite`. Normalize with `.replace(tzinfo=timezone.utc)` before Python comparisons.
7. **Database Decoupling:** The Discord bot does not query Postgres directly in production (`usePostgres = false`). It proxies shared state via signed HMAC requests (`callMotherboard`) to Motherboard APIs.
8. **Dual Approval Persistence Pattern:** Money requests >= ₹1L require two distinct approvers (OKF Rule 35). Approvals are persisted as append-only `AuditLog` rows (`action=finance.request.approval_recorded`) and counted via `COUNT(DISTINCT actor_id)`.

---

## 4. Subsystem Specifications

### 4.1 IAM (Identity & Access Management)
- Principal resolver (`principal.py`) resolves user + inherited group permissions.
- Evaluator (`policy.py`) exposes `can(user, perm, resource)`, `require_permission(perm)`, `batch_can(user, perms)`.
- Visual hierarchy at `/dashboard/iam` (`IAMHierarchyVisualizer.tsx`) maps Discord roles to system roles (`Super Admin -> Executive -> Lead -> Member -> Bot`).

### 4.2 Meetings & Chrono v2 Engine
- **Unification:** Both dashboard (`/dashboard/meetings`) and public booking portal (`cal.gobitsnbytes.org`) use Motherboard `/api/meetings` APIs.
- **Availability:** `AvailabilityGrid.tsx` serializes 7-day schedule JSON. Public `/hosts` and `/{slug}/slots` calculate timezone and meeting overlaps.
- **Persistence & OTP:** `GuestVerification` model (`a9c4e7f1b2d6`) stores SHA-256 hashed OTPs (1h TTL). `meetings.recording_metadata` JSON stores audio duration/size.
- **RSVP Widget:** RFC-2446 `multipart/alternative` + `text/calendar; method=REQUEST` MIME generation for native 1-click Gmail/Outlook calendar RSVPs.
- **Transcription:** Fallback pipeline: Gemini 3.5 Flash $\rightarrow$ Gemini 2.5 Flash $\rightarrow$ structured JSON briefs & action items (`/action-items/mine`).

### 4.3 Finance & Double-Entry Ledger
- **Self-Approval Prohibition:** HTTP 403 when `requester_id == actor_id` (IOM v2.0 §3.2).
- **Dual Authorization Band:** Requests $\ge$ ₹1L require 2 distinct approvers before funds move (OKF Rule 35).
- **Section 8 Compliance:** `GET /api/finance/compliance` delivers live compliance attestations, active FY labels (Apr 1–Mar 31), and audit counts.
- **Adapter Seam:** `RazorpayXAdapter` protocol (`PaperLedgerAdapter` for DB virtual accounts; `RazorpayXLiveAdapter` stub for future API activation).
- **FY CSV Export:** `GET /api/finance/reports/fy?fy=YYYY-YY` streams chunked ledger transactions.

### 4.4 Digital Signatures & Legal Agent (`bnb-signatures`)
- **Signature Engine:** PyMuPDF preview/overlay generator, `.docx` to PDF conversion, SHA-256 tamper-evident sealing, and Audit Certificates.
- **Security & DSC:** 6-digit email OTP (2-min expiry), Class 1/2/3 USB token & PKCS#12 `.pfx` software certificate signing (`e5f6a1b2c3d4`).
- **Statutory Framework:** Aligned with IT Act 2000 Sec 10A (electronic contracts) and BSA 2023 Sec 63 (forensic electronic records).
- **Quash / Void & Purge:** `POST /void` invalidates active signing tokens with immutable audit entries; `DELETE` generates a downloadable Certificate of Cancellation before purging disk files.
- **Legal Agent (`legal@gobitsnbytes.org`):** IMAP inbox poller, automatic clause risk analysis (OKF rules), RAG `/ask` over executed contracts, and 3/7/14-day automated signing reminder nudges.

### 4.5 Swiss Neobrutalism Design System
- **Core Tokens:** 2px solid borders (`border-2 border-border`), boxy corners (`rounded-base`), hard offset drop shadows (`shadow-shadow`), dark backgrounds (`#0d0d10`, `#141418`).
- **Typography:** Anton (`font-heading font-black`) for headers, Inter (`font-base`) for UI controls, JetBrains Mono (`font-mono`) for coordinates and metrics, Merriweather for long-form prose.
- **Branding Palette:** Core Burgundy (`#97192C`), Pop Orange (`#FC920D`), Dark Neutral (`#120F0A`), Warm Blank (`#FAF8F5`).

---

## 5. Alembic Migration History

| Migration ID | Description |
|---|---|
| `initial_schema` | Core 13 tables (users, groups, permissions, grants, forks, audit_logs, events, virtual_accounts, etc.) |
| `a1b2c3d4e5f6` | Added `calcom_booking_id` and `calcom_uid` to `EventCache` and meetings schema. |
| `f1a2b3c4d5e6` | Added Digital Signatures tables (`signature_requests`, `recipients`, `fields`, `audit_logs`). |
| `e5f6a1b2c3d4` | Added DSC certificate columns (`dsc_type`, `dsc_issuer`, `dsc_serial`, `allowed_sig_type`). |
| `a7f3c92b1d84` | Contract Assistant ORM tables & clause findings. |
| `h1i2j3k4l5m6` | Dyslexic CRM tables & lead tracking models. |
| `a9c4e7f1b2d6` | Added `guest_verifications` table (hashed OTPs) and `meetings.recording_metadata` JSON column. |

---

## 6. Audit Findings & Production Priorities

Comprehensive read-only production audits (S62–S63) established the following priority backlog for future rollout phases:

1. **Finance & Banking:**
   - Implement real double-entry journal lines (immutable credit/debit pairs) and reconcile historical opening balances.
   - Complete live RazorpayX payout/contact integration with HMAC webhook signature validation.
2. **Signatures & Legal Evidence:**
   - Strengthen public verification endpoints with rate limiting and signed session tokens.
   - Enforce mandatory org countersignature in final completion workflow before sealing.
   - Update compliance copy to reference BSA 2023 Section 63 certificate requirements.
3. **Meetings & Scheduling:**
   - Ensure PostgreSQL is the single source of truth for the bot scheduler to prevent SQLite mirror split-brain.
   - Enforce database-level UNIQUE constraints on `calcom_booking_id` to eliminate poll duplication.
   - Add rate-limiting and server-side slot verification to public booking endpoints.
4. **Plugins:**
   - Enforce explicit `*.admin` permission checks on destructive routes across all plugin manifests.

---

## 7. Session Log

### Pre-Production (S1–S33, up to 2026-06-25)
- Scaffolding, Phase 1 (13 ORM tables), Phase 2 (IAM), Phase 3 (EventBus), Phase 4 (Plugin SDK), Phase 7 (Finance shell), VPS deployment, Nginx SSL.

### S34–S44 (2026-06-26 to 2026-07-19)
- **S34–S36:** Discord bot refactored to proxy all operations to Motherboard via HMAC `callMotherboard`; audio transcription offloaded to FastAPI; Bun test suite hardened (208/208 green).
- **S37–S39:** Cal.com rescheduling webhook (`BOOKING_RESCHEDULED`); voice channel auto-join cache resolution; Docker compose Redis URL fix.
- **S40–S41:** Meetings N+1 query optimization; Cal.com schema migration (`a1b2c3d4e5f6`); Gemini 3.5 $\rightarrow$ 2.5 Flash transcription fallback; programmatic API key auth.
- **S42–S44:** Consolidated bot into monorepo (`apps/bot`); migrated SQLite to `bun:sqlite`; built public availability slots API; RFC-2446 email RSVP widget.

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

### 2026-09-09 — IAM + Control Room Overhaul Phase

- Read the brand guideline and established `PRODUCT.md` / `DESIGN.md` as the working product and visual contract: warm editorial surfaces, burgundy control-room rail, orange signal color, crisp borders, explicit city/global scope, keyboard-first and WCAG AA behavior.
- Reworked IAM around explainable, city-scoped access: active/non-expired principal resolution, fail-closed service identity, mixed-credential rejection, grant validation, mutation audit entries, and scope-preserving `batch_can` behavior. Focused IAM/auth suites and the full API suite pass (`103 passed`).
- Rebuilt the IAM overview UI with effective access, scope explanation, group search, loading/error states, and safer Discord mapping feedback.
- Reworked the dashboard shell across overview, meetings, members, finance, IAM, audit, and settings with a consistent branded control-room frame while preserving dark high-density workflows where they are intentional.
- Repaired the workspace install state with `bun install --frozen-lockfile`; the full production web build now passes. Web typecheck passes.
- Smoke-tested all main routes locally. Unauthenticated requests correctly land on local `/login`; `/api/auth/session` returns 200 when the local runtime is started with the configured secret. Production deployment and Discord RLVR testing remain intentionally deferred until the broader overhaul is complete.
- Continued the shell pass through Finance: unified the portal frame with the burgundy rail and warm workspace, and corrected finance page titles/subtitles for readable contrast on the new surface. Typecheck and `git diff --check` remain clean.
- Reworked Members and Audit into operator-grade surfaces: typed records, explicit retryable errors, skeleton loading, honest empty states, branded summaries, and accessible table captions. This slice is ready for its own review/build/deploy checkpoint.
