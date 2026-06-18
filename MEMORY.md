# Motherboard Operations Platform — Agent Memory

Persistent log of tasks, decisions, and workspace status. Every agent invocation updates this file for continuity.

---

## 1. Project Status

- **Current Phase:** Phase 3 (Event Bus `apps/api/app/events`)
- **Next Milestone:** Plugin SDK

### Milestone Checklist

- [x] **Phase 0: Repository Scaffolding** ✅
- [x] **Phase 1: Database Schema** ✅ — 13 ORM tables, Alembic, idempotent seeder (15 groups, 23 permissions, 15 role mappings, 12 forks), 8 active routers, CORS, lifespan auto-migrate+seed
- [x] **Phase 2: IAM Module** ✅ — Principal resolver, policy evaluator (`can`/`require_permission`/`batch_can`), audit writer, constants, schemas, router (iam.py — registered in main.py), pytest suite
- [ ] **Phase 3: Event Bus** (`apps/api/app/events`)
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

### 2026-06-18

**S18 — Phase 5 Provisioning Worker:** Created custom errors (`errors.py`), Discord API client with pagination & rate limit backoff (`client.py`), core sync engine (`sync.py`), and APScheduler integration (`scheduler.py`) under `apps/api/app/provisioning/`. Fixed 3 bugs in existing IAM router (`iam.py`) and registered it along with the provisioning sync router in `main.py` lifespan. Added `aiosqlite` dependency for in-memory SQLite testing. Created full unit/integration test suites for Discord client and sync worker, showing 100% green test pass.

**S19 — Database & Seeder Audit Fixes:** Switched to new branch `akshat/fixes`, performed a database/seeding audit, implemented symmetric token encryption (`EncryptedString` using Fernet) in `models.py`, refactored `seeder.py` to be dialect-independent (SQLite-compatible), added `clear_db_cache` helper to `database.py`, fixed test-suite mock configuration in `conftest.py`, and added verification tests in `test_encryption.py`.

**S20 — Database & IAM Audit Fixes Refinement:** Completed full audit and applied fixes for both Database/Seeder and IAM (Phase 2). Cleared database and settings caches during test runs, and shifted test database targets from `:memory:` to isolated file-based databases (`test_temp_router.db` and `test_temp_phase1.db`) to allow running FastAPI lifespans and fixtures against the same database. Refactored the seeder to support SQLite JSON bindings for raw SQL inserts, converted models to use generic `JSON` columns compiling to `JSONB` on Postgres and `JSON` on SQLite, resolved the FastAPI dependency overrides issue for `get_db_session`, and skipped Alembic migrations in tests. Added comprehensive integration tests in `test_iam_router.py` to test `/me`, `/groups` slugification, and `/discord-mappings` priorities. All 45 backend tests are passing 100% green. Pushed to `origin/akshat/fixes`.

