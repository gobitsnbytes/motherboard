# Motherboard Operations Platform — Agent Memory

Persistent log of tasks, decisions, and workspace status. Every agent invocation updates this file for continuity.

---

## 1. Project Status

- **Current Phase:** Phase 4 (Plugin SDK `apps/api/app/plugin_sdk`)
- **Next Milestone:** Provisioning Worker

### Milestone Checklist

- [x] **Phase 0: Repository Scaffolding** ✅
- [x] **Phase 1: Database Schema** ✅ — 13 ORM tables, Alembic, idempotent seeder (15 groups, 23 permissions, 15 role mappings, 12 forks), 8 active routers, CORS, lifespan auto-migrate+seed
- [x] **Phase 2: IAM Module** ✅ — Principal resolver, policy evaluator (`can`/`require_permission`/`batch_can`), audit writer, constants, schemas, router (iam.py — not yet registered in main.py), pytest suite
- [x] **Phase 3: Event Bus** ✅ — Redis pub/sub EventBus, Typed Event Schemas, lifespan integrated
- [ ] **Phase 4: Plugin SDK** (`apps/api/app/plugin_sdk`)
- [x] **Phase 5: Provisioning Worker** (`apps/api/app/provisioning`) ✅ — Discord sync worker, client, sync logic, APScheduler periodic sync integration, sync router integration, test suite
- [x] **Phase 6: Shared UI** (`@bnb/ui`) ✅ — 38 shadcn/neobrutalism components, barrel exports (sidebar/resizable/form excluded due to SSR)
- [ ] **Phase 7: Web Dashboard** (`apps/web`) — shell + NextAuth v5 + landing page + `/finance` placeholder done
- [ ] **Phase 8: Core Plugins**
- [ ] **Phase 9: Docker Production**

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
  app/routers/     — 8 active routers + iam.py (unregistered)
  app/schemas/     — Pydantic v2 request/response schemas
packages/ui  — 38 shadcn/neobrutalism React components
plugins/     — First- and third-party plugins (reserved, empty)
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

### 2026-06-16

**S1 — Scaffolding:** Initialized Bun + Turborepo workspace. Scaffolded all 8 packages/apps, Docker configs, `.env.example`. Phase 0 complete.

### 2026-06-17

**S2 — Skills & Docs:** Added AI agent skill guidelines to AGENTS.md (matching `.agents/skills/` on disk). Integrated Discord role hierarchy from `role_structure.md` into AGENTS.md + techspec.md. Created README.md, brandkit.md.

**S3 — Neo-Brutalist UI:** Configured `@bnb/ui` for shadcn. Installed all neobrutalism components (38). Created design.md. Added `class-variance-authority` + Radix primitives.

**S4–S6 — Skills & Roadmap:** Added `database-migrations-sql-migrations`, `finance-billing-ops`, `nextjs-best-practices` skills. Created roadmap.md (5 stages).

**S7 — Legal Wiki:** Consolidated 16 Notion wiki files into `legal_governance_rules.md`. Added `fastify-best-practices` skill.

**S8 — Fastify→FastAPI Migration:** Migrated backend stack rules to FastAPI/Python. Deleted obsolete Node.js/Fastify skill folders. Created `cors_security_guide.md`.

**S9 — Techspec Rewrite:** Rewrote techspec.md for FastAPI. Selected async SQLAlchemy 2.0 + Alembic. Synced AGENTS.md spec. Deleted obsolete Drizzle skills.

**S10 — Phase 0 Planning:** Identified repo still contained old TS packages. Planned FastAPI realignment.

**S11 — Phase 0 Execution:** Deleted 5 obsolete TS packages (`packages/db`, `iam`, `events`, `plugin-sdk`, `provisioning`). Removed Fastify scaffold from `apps/api`. Verified Python/uv layout.

**S12 — Landing Page:** Built cinematic space-travel landing page with FadingVideo, BlurText, HeroSection, CapabilitiesSection. Added framer-motion + liquid-glass CSS. Build passes.

**S13a — Phase 1 Database:** Created models.py (13 tables), seed_data.py, seeder.py. Updated main.py (lifespan, CORS, 7 routers), config.py, dependencies.py. Wrote 7 routers + 6 schema files. Set up Alembic. All 13 tables live in Postgres. Committed 29 files on `db/init-schema`.

**S13b — Landing Page Refinements:** Removed CTAs, fixed liquid-glass visibility, optimized FadingVideo with hardware-accelerated looping, added org links.

**S14 — Doc Cleanup:** Consolidated brandkit.md → design.md. Stripped duplicate spec from AGENTS.md. Added documentation index.

**S15 — Dashboard Shell:** Set up NextAuth v5 (Discord OAuth, fire-and-forget upsert). Created dashboard layout, sidebar, topbar, 5 placeholder pages, login page. Fixed SSR crash from `transpilePackages` + `@bnb/ui` barrels. Build: 11 routes, 0 errors.

**S16a — Phase 2 IAM:** Created policy.py (`can`, `require_permission`, `batch_can`), constants.py, audit.py, schemas/iam.py, routers/iam.py, tests/test_iam_policy.py.

**S16b — Finance Module:** Created routers/finance.py (`/api/finance/*` — health + info). Registered in main.py. Created `/finance` "Coming Soon" page. Updated README, AGENTS, MEMORY.

**S17 — Documentation Sync:** Reviewed all .md files against actual code. Fixed: MEMORY.md workspace layout + counts, models.py phantom `sessions` table, techspec.md (title + 6 code sections), cors_security_guide.md (Fastify ref + endpoint paths), AGENTS.md (added IAM section), apps/api/README.md (expanded from 7→61 lines). Fixed "14 tables" → "13 tables" in techspec. Fixed router count "9" → "8 active + iam unregistered".

**S18 — Event Bus:** Implemented Phase 3 Event Bus (`apps/api/app/events`). Added Typed Schemas, integrated Asyncio & Redis Pub/Sub, hooked into FastAPI lifespan via `main.py`.

**S19 — Infrastructure Unification & Bugfixes:** Fixed FastAPI/Alembic multi-threaded locking deadlock on boot. Patched Dockerfiles to include `alembic` migrations. Hardened EventBus with auto-reconnect and health checks over Docker bridge. Unified Next.js reverse proxy on port 8000 and fixed 307 trailing slash redirects from FastAPI leaking internal hostnames.
**S19 — Database & Seeder Audit Fixes:** Switched to new branch `akshat/fixes`, performed a database/seeding audit, implemented symmetric token encryption (`EncryptedString` using Fernet) in `models.py`, refactored `seeder.py` to be dialect-independent (SQLite-compatible), added `clear_db_cache` helper to `database.py`, fixed test-suite mock configuration in `conftest.py`, and added verification tests in `test_encryption.py`.

**S20 — Database, IAM & Provisioning Audit Fixes:** Completed full audits and applied fixes across Database/Seeder (Phase 1), IAM (Phase 2), and Provisioning Worker (Phase 5). Configured cache clearing and shifted test database targets to isolated files (`test_temp_router.db` and `test_temp_phase1.db`) to allow running FastAPI lifespans and fixtures against the same database. Converted models to use generic `JSON` columns compiling to `JSONB` on Postgres and `JSON` on SQLite, resolved the FastAPI dependency overrides issue for `get_db_session`, and skipped Alembic migrations in tests.
In the Provisioning Worker (Phase 5), optimized memory and database overhead by scoping `DiscordAccount` and `Membership` queries using `.in_` clauses on the active Discord guild member list, and added validation checks to prevent APScheduler from running without proper guild/bot configurations.
Added comprehensive integration tests in `test_iam_router.py` to test `/me`, `/groups` slugification, and `/discord-mappings` priorities. All 45 backend tests are passing 100% green. Pushed to `origin/akshat/fixes`.

**S21 — Rigorous Backend API & Security Testing:** Expanded the backend test suite with 30 new integration and security test cases, raising the total test count from 45 to 75 (100% green).
- Created `test_cors.py` validating CORS allowed/disallowed/null origins, preflight requests, and prefix/suffix bypass attempts.
- Created `test_users_router.py` testing User CRUD, soft deletions, and invalid UUID formats.
- Created `test_groups_router.py` testing Group/Membership CRUD, system group modifications protection (403), slug conflicts, and duplicate memberships.
- Created `test_forks_router.py` testing Fork CRUD, contributor tracks, and active members listing.
- Created `test_sync_router.py` testing manual sync triggers, permission gates (trigger/read), background task enqueuing, and super admin bypasses.
- Created `test_audit_plugins_health.py` testing health checks, pagination/filtering on audit logs, and plugin registry configurations.
Surfaced architectural findings regarding unauthenticated endpoints in the users, groups, forks, audit, and plugins routers.
### 2026-06-19

**S22 — Finance Ledger & Card Simulation:** Completed Phase 7 Finance implementation (virtual accounts, virtual cards, double-entry ledger transactions, money requests, limits validation, and merchant charge simulation).
- **Models & Migration:** Added `VirtualTransaction` model and `daily_limit_paise` / `monthly_limit_paise` columns on `VirtualCard`. Generated and executed Alembic schema migrations.
- **Backend Endpoints:** Implemented transactional ledger logs for Money Request approvals, card limit checks (daily/monthly calendar/rolling hours), and an atomic merchant charge simulation endpoint (`POST /api/finance/cards/{card_id}/simulate-charge`). Added global recent transactions list API (`GET /api/finance/transactions`).
- **Test Suite:** Added comprehensive unit and integration tests in `test_finance_ledger.py` covering double-entry transactions, approval gates, limit breaches, and charge simulation. All 76 backend tests pass.
- **Frontend Pages:** Rendered double-entry transaction ledgers on Account Details (`/finance/accounts/[id]`) and global Recent Ledger Transactions on Dashboard (`/finance/dashboard`). Updated Virtual Cards (`/finance/cards`) tab to configure daily/monthly spending limits and trigger merchant charge simulations with feedback modals.
- **Frontend Compilation & Dependency Fixes:**
  - Fixed a nested JSX ternary syntax error in `/finance/cards/page.tsx` by properly closing the empty-state conditional branch and inserting the `else` colon.
  - Linked missing local workspaces and third-party dependencies (`next-auth` and `framer-motion`) by executing a clean `bun install` at the root workspace.
  - Resolved `fetch` option type checking errors across all 5 `/finance` subpages by explicitly annotating the return type of `getHeaders()` helper methods as `Record<string, string>`. Next.js production build now compiles 100% successfully.

### 2026-06-20

**S23 — Database Seeding & OpenAPI Routing Fixes:** Resolved database insertion error on container startup and fixed Swagger UI openapi.json 404 errors.
- **Database Seeding Fix:**
  - **Root Cause:** Raw SQL queries executed via `session.execute(text(...))` bypass SQLAlchemy's column-level type processors (which serialize dicts to strings for JSON columns). During prepare, Postgres/asyncpg resolved the target parameter as JSONB and invoked its registered codec, which expected a serialized string to `.encode()`. Passing a raw Python `dict` directly caused `AttributeError: 'dict' object has no attribute 'encode'`.
  - **Fix implemented:** Imported the `json` module in [seeder.py](file:///home/equation/Projects/motherboard/apps/api/app/db/seeder.py) and changed the `:metadata` bind parameter to pass `json.dumps(fork.get("metadata", {}))` directly, satisfying both SQLite and PostgreSQL.
  - **Verification:** Ran `uv run pytest` (76/76 green), built and restarted the containers via `docker compose up --build -d`, and successfully verified table counts (`12` forks, `15` groups) directly in the Postgres container.
- **OpenAPI / Swagger UI Routing Fix:**
  - **Root Cause:** Next.js proxies API requests starting with `/api/` to the FastAPI backend. However, FastAPI's default Swagger UI makes a client-side request to `/openapi.json` relative to the server root (i.e. `http://localhost:8000/openapi.json`), which bypasses the Next.js `/api/` prefix matching and returns a 404 from Next.js.
  - **Fix implemented:** 
    1. Adjusted Next.js's fallback rewrite in [next.config.js](file:///home/equation/Projects/motherboard/apps/web/next.config.js) to preserve the `/api` prefix when proxying requests to the backend (`destination: .../api/:path*` instead of `.../:path*`) to properly align with FastAPI's router prefixes.
    2. Configured the `openapi_url`, `docs_url`, and `redoc_url` parameters on the `FastAPI` instance in [main.py](file:///home/equation/Projects/motherboard/apps/api/app/main.py) to be prefixed with `/api` (e.g. `/api/openapi.json`, `/api/docs`, and `/api/redoc`).
  - **Verification:** Verified `/api/docs` and `/api/openapi.json` resolve correctly with `200 OK` from Uvicorn, and ran the backend test suite successfully (76/76 green).
