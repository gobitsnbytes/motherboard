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

**S24 — Priority Bugfix Implementation:** Implemented the 10-bug hardening plan covering backend auth, protected routers, finance ledger invariants, frontend proxying, finance UI request filtering, CORS configuration, and setup docs.
- **Backend Auth:** Replaced spoofable `X-User-Id` trust with signed internal proxy headers (`X-Internal-User-Id`, `X-Internal-Timestamp`, `X-Internal-Signature`) validated with HMAC and timestamp freshness. Added trusted `/api/auth/upsert` Discord identity bridge using `X-Internal-Secret`.
- **Authorization:** Protected legacy users, groups, forks, audit, and plugins routers with IAM permission checks. Aligned IAM permission checks for permission registry and Discord role mapping routes with seeded permission names.
- **Finance Integrity:** Locked money requests/accounts/cards during approvals and simulated charges, rejected transfers from empty source accounts, and preserved non-negative source balances. Added regression coverage for the insufficient-source case.
- **Frontend:** Added a same-origin Next.js `/api/[...path]` proxy that signs backend requests with the internal user id from the NextAuth session. NextAuth sign-in now blocks unless backend upsert succeeds and stores `internalUserId` in the JWT/session. Finance pages now call same-origin `/api/*`, removed `localStorage` auth headers, fixed the requests `all` tab query, and filtered account-detail requests by source or destination account.
- **CORS & Docs:** `CORS_ORIGINS` is now parsed as a comma-separated override, falling back to `NEXTAUTH_URL`; README API docs URL now points to `/api/docs`.
- **Verification:** `uv run pytest -q` in `apps/api` passes (79/79). `git diff --check` is clean apart from Git line-ending warnings. `npm run typecheck --workspace @bnb/web` is blocked locally because dependencies are not installed and `tsc` is unavailable; the repo declares `bun@1.3.11`, but `bun` is not installed in this environment.
### 2026-06-20 (Later)

**S25 — Full App End-to-End Audit & Live Testing:** Ran comprehensive test/debug/check across all 10 phases, including live API endpoint testing via ASGI transport.

**Bugs found & fixed:**
1. **Missing `plugins/` directory** (referenced in Bun workspace but didn't exist) — created.
2. **`sa.text('now()')` in initial alembic migration** — Alembic migration `3de79b987bc8` used `sa.text('now()')` for all `server_default` timestamp columns. This works on PostgreSQL but SQLite does not support `now()` as a DEFAULT expression. SQLAlchemy's ORM models use `func.now()` which correctly compiles to `CURRENT_TIMESTAMP` for SQLite, but `sa.text()` passes raw SQL verbatim.  
   *Fix:* Replaced all 19 occurrences of `sa.text('now()')` with `sa.text('CURRENT_TIMESTAMP')` in `apps/api/alembic/versions/3de79b987bc8_initial_schema.py`. The finance migrations (`e3d851ea9d54`, `cdd5a04f9914`) already used `(CURRENT_TIMESTAMP)` and were unaffected.
3. **`DATABASE_URL` not propagated to os.environ for Alembic** — The lifespan in `main.py` runs Alembic migrations programmatically via `AlembicConfig`. But `alembic/env.py` reads `DATABASE_URL` from `os.environ`, while pydantic-settings reads from `.env` without exporting to `os.environ`. When the `DATABASE_URL` is only set in `.env` (not as an actual env var), Alembic falls back to the hardcoded `driver://user:pass@localhost/dbname` from `alembic.ini` and crashes.  
   *Fix:* Added `_ensure_alembic_env()` helper in `main.py` that exports critical env vars (starting with `DATABASE_URL`) from pydantic-settings to `os.environ` before running migrations.

**Live endpoint testing results** (ASGI transport against SQLite):
```
HEALTH: 200              OPENAPI: 200 (39 paths)
CREATE USER: 201         USERS LIST: 200
GROUPS: 200/200          FORKS: 200 (12 seeded)
FINANCE HEALTH: 200      FINANCE INFO: 200
SYNC RUNS: 401/403       AUDIT LOGS: 200
PLUGINS: 200             IAM/ME: 401/200
IAM PERMISSIONS: 403     CORS: 200/200
```

**Docker verification:** Docker Desktop engine is available but wasn't fully ready for builds during this session. Dockerfiles (`api.Dockerfile`, `web.Dockerfile`) and compose files (`docker-compose.yml`, `docker-compose.prod.yml`) were verified at code level — correct structure, proper alembic inclusion, proper environment variable wiring.

**Full verification results:**
- Backend tests: **76/76 passing** (11.50s, no regressions)
- Frontend build: **17 routes, 0 errors** (3.0s)
- Live API endpoints: **18/18 responding correctly** (auth-gated endpoints return proper 401/403)
- Source files: All phases audited, 3 bugs fixed

### 2026-06-23

**S26 — VPS Deployment & CI/CD Pipeline Setup:**
- **SSH & SSH Keys Verification:** Verified SSH access to the VPS (`161.118.162.166`) using the existing key. Confirmed `deploy` user is correctly configured.
- **Setup Script Updates (`deploy/api/setup.sh`):**
  - Switched the clone command to HTTPS (`https://github.com/gobitsnbytes/motherboard.git`) since cloning via SSH fails without a configured deploy key on GitHub.
  - Improved the `authorized_keys` copying logic to prioritize copying the clean public key from `/home/ubuntu/.ssh/authorized_keys` (or filter out restricted root key warnings), resolving a lockout issue for the `deploy` user.
- **Verification:**
  - Manually fixed the `deploy` user's `authorized_keys` on the VPS to remove the root command restriction.
  - Confirmed the `deploy` user can log in to the VPS via SSH.
  - Ran the backend test suite: **82/82 tests passed** (15.92s).

**S27 — CI/CD Pipeline & Permissions Fixes:**
- **CI/CD Pytest Configuration:**
  - Fixed the backend test runner in `.github/workflows/deploy-api.yml` by adding `working-directory: apps/api` and running `uv run python -m pytest`. Running pytest inside `apps/api` ensures it discovers and loads `apps/api/pytest.ini` (`asyncio_mode = auto`), resolving `async def functions are not natively supported` failures.
- **Script Executable Permissions & VPS Workaround:**
  - Staged file mode changes (`100755` executable bit) for `deploy/api/deploy.sh` and `deploy/api/setup.sh` in the Git index using `git update-index --chmod=+x`.
  - Manually marked `deploy.sh` and `setup.sh` as executable on the VPS using SSH: `chmod +x /opt/bnb-api/deploy/api/*.sh`.
  - Hardened `.github/workflows/deploy-api.yml` to call `bash /opt/bnb-api/deploy/api/deploy.sh` directly, removing execution-bit dependency on checkout.
- **Verification:**
  - Verified local pytest run (82/82 green). Staged and committed files, pushed to `prod` branch.
- **Versioning (v0.1.1):**
  - Bumped version to `0.1.1` in `apps/api/pyproject.toml`, FastAPI configuration in `apps/api/app/main.py`, `apps/web/package.json`, and `packages/ui/package.json`. Synced and updated lockfiles.
- **Alembic & Deploy script Env Hardening:**
  - Integrated `python-dotenv` inside `apps/api/alembic/env.py` to automatically load environment variables (falling back to `/opt/bnb-api/.env` on the VPS) to avoid database connection failure if environment variables are not pre-exported.
  - Hardened `deploy/api/deploy.sh` to load and parse `.env` files using a robust `while-read` loop that handles spaces, quotes, and special characters cleanly (preventing ampersand and bracket failures in SMTP configurations).

### 2026-06-23 (Later)

**S28 — NextAuth Fix & Rigorous Live API Testing:**
- **NextAuth Fix:** Explicitly passed `clientId` and `clientSecret` referencing `process.env.DISCORD_CLIENT_ID` and `process.env.DISCORD_CLIENT_SECRET` to the Discord provider options in [auth.ts](file:///d:/motherboard/apps/web/lib/auth.ts). This resolves the `client_id` being `"undefined"` as a string and returning the `"Value \"undefined\" is not snowflake"` error from Discord's API. Supported fallbacks to default `AUTH_DISCORD_ID` / `AUTH_DISCORD_SECRET` env variables and configured Turborepo `globalEnv` in [turbo.json](file:///d:/motherboard/turbo.json).
- **Vercel Production Branch Git Config:** Created [vercel.json](file:///d:/motherboard/vercel.json) at the repository root to configure Vercel to treat the `prod` branch as the official Production Branch for automatic deployment.
- **Redis Timeout Log Fix:** Patched [bus.py](file:///d:/motherboard/apps/api/app/events/bus.py) to gracefully catch `redis.exceptions.TimeoutError` and `asyncio.TimeoutError` from the Upstash Redis listener during inactive periods, pinging the connection and looping back cleanly without log pollution or connection churn.
- **Rigorous Live API Testing ([live_audit.py](file:///d:/motherboard/apps/api/live_audit.py)):**
  - Created and executed a rigorous, self-contained auditing script targeting `https://api.gobitsnbytes.org`.
  - Audited and passed tests for:
    1. **Public endpoints:** `/health`, `/api/finance/health`, and `/api/finance/info` to ensure uptime and correct payload structures.
    2. **OpenAPI definition:** `/api/openapi.json` to ensure valid spec formatting.
    3. **IAM security gates:** `/api/users/`, `/api/groups/`, `/api/forks/`, `/api/iam/discord-roles`, `/api/finance/accounts`, `/api/sync/runs` to ensure missing, malformed, stale, or tampered HMAC signature requests get blocked with `401 Unauthorized` responses.
    4. **CORS validation:** Verified that disallowed origins (like `https://evil.com`) do not receive CORS headers.
- **Verification:**
  - Ran `live_audit.py` showing all checks passed against the live environment.
  - Ran the local test suite: **82/82 tests passed** (10.04s).

### 2026-06-25

**S29 — Plugin SDK Implementation & Next.js Dynamic Sidebar Integration:**
- **Dynamic Plugin SDK**: Created `types.py` (Pydantic lifecycle schemas) and `loader.py` (dynamic `PluginLoader`) in `apps/api/app/plugin_sdk`. The loader dynamically discovers plugins, registers/seeds manifest definitions in `plugin_registry` and `permissions` tables, mounts routers, and runs `on_load` and `on_unload` lifespan hooks.
- **Lifespan Integration**: Integrated `PluginLoader` and periodic `Discord` sync worker scheduler inside FastAPI `main.py` lifespan events.
- **Active Plugins API**: Exposed the list of active plugin manifests and their UI panels via `GET /api/plugins/active` in the plugins router.
- **Sample Plugin**: Created `@bnb-plugins/sample_plugin` containing workspace configuration, backend API endpoints, custom permissions, and a dynamic Neo-Brutalist React UI that fetches data from the dynamic plugin API.
- **Next.js Integration**: Mapped `@bnb-plugins/*` paths inside Next.js `tsconfig.json`. Created client page `apps/web/app/dashboard/plugins/[pluginId]/[[...slug]]/page.tsx` for dynamic mounting, and updated `Sidebar.tsx` to dynamically query active plugins and render their panels under a "Plugins" navigation section.
- **Verification**: Added 4 new integration/unit tests in `test_plugins.py`, raising total test coverage to 86 tests (100% green). Verified the complete Turborepo compilation succeeds cleanly under Bun workspaces.




