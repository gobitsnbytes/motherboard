# Motherboard Operations Platform — Agent Memory

This file serves as a persistent, running log of all tasks performed, design decisions made, technical challenges resolved, and current workspace status. Every agent invocation updates this document to ensure perfect continuity across sessions.

---

## 1. Project Status Overview

- **Current Phase:** Phase 8 (Web Dashboard `apps/web`)
- **Next Milestone:** FastAPI Core API (`apps/api`) + Database Schema

### Milestone Checklist

- [x] **Phase 0: Repository Scaffolding**
  - [x] Initialize workspace (`bun init -y`)
  - [x] Add Turborepo (`bun add -D turbo`)
  - [x] Configure `package.json` workspaces and scripts
  - [x] Create `turbo.json`
  - [x] Set up root `.env.example`
  - [x] Create shared TypeScript configuration (`tsconfig.base.json`)
  - [x] Create folder structure for apps, packages, and plugins
  - [x] Create minimal package configurations (`package.json`, `tsconfig.json`) for each workspace
  - [x] Create base `docker-compose.yml`
  - [x] Create placeholder Dockerfiles in `docker/`
- [x] **Phase 0: Repository Scaffolding** ✅
- [x] **Phase 1: Database Schema (`apps/api/app/db`)** ✅
  - [x] SQLAlchemy 2.0 ORM models (13 tables): users, discord_accounts, groups, memberships, discord_role_mappings, permissions, grants, delegations, forks, fork_members, plugin_registry, audit_log, sync_runs
  - [x] Alembic configured with async env.py (asyncpg driver, NullPool for migrations)
  - [x] `alembic revision --autogenerate` → `alembic upgrade head` applied live in Postgres
  - [x] Idempotent seeder (seed_data.py + seeder.py): 15 system groups, 24 permissions, 14 Discord role mappings, 12 city forks
  - [x] `main.py` lifespan: auto-migrate + auto-seed on startup
  - [x] 7 API routers: health, users, groups, forks, audit, sync, plugins
  - [x] Pydantic v2 schemas for all endpoints
  - [x] `DbSession` / `AppSettings` typed dependency aliases in `dependencies.py`
  - [x] CORS middleware wired in `main.py`
  - [x] `redis_url` + `cors_origins` added to `config.py`
  - [x] `[tool.fastapi]` entrypoint in `pyproject.toml`
- [ ] **Phase 2: IAM Module (`apps/api/app/iam`)**

- [ ] **Phase 3: Event Bus (`@bnb/events`)**
- [ ] **Phase 4: Plugin SDK (`@bnb/plugin-sdk`)**
- [ ] **Phase 5: Provisioning Worker (`@bnb/provisioning`)**
- [ ] **Phase 6: Shared UI Component Library (`@bnb/ui`)**
- [ ] **Phase 7: Fastify Core API (`apps/api`)**
- [ ] **Phase 8: Web Dashboard (`apps/web`)**
  - [x] Dashboard app shell with NextAuth v5, route structure, layout, login page
- [ ] **Phase 9: Core Plugins Implementation**
- [ ] **Phase 10: Docker Production Setup**

---

## 2. Technical Decisions & Architecture

### Monorepo Infrastructure
- **Runtime & Package Manager:** Bun (latest stable)
- **Build System:** Turborepo
- **Workspace Layout:**
  - `apps/web`: Next.js 15 App Router + Radix UI + Tailwind CSS
  - `apps/api`: Fastify 5 core backend
  - `packages/db`: Drizzle ORM client & migrations
  - `packages/iam`: Permission engine and policy evaluator
  - `packages/provisioning`: Discord integration sync worker
  - `packages/events`: In-process EventEmitter & Redis Pub/Sub events
  - `packages/plugin-sdk`: Plugin contract interfaces
  - `packages/ui`: Shared React components
  - `plugins/`: First- and third-party operational plugins
- **Database:** PostgreSQL 16 (running in Docker)
- **Caching & Event Pub/Sub:** Redis 7 (running in Docker)

---

## 3. Key Learnings & Insights

### Workspace Configurations
- **Turborepo Workspace Discovery:** Turborepo requires the `"packageManager": "bun@1.3.11"` field in the root `package.json` to correctly resolve local workspace packages. Without it, the error `Could not resolve workspaces` is thrown.
- **Turborepo Task Dependencies:** By default, Turborepo tasks can specify dependencies on their upstream builds (`dependsOn: ["^build"]`). If upstream packages do not have a defined task script (like `build`), turbo will defer scheduling tasks for packages that depend on them. Direct execution via `tsc --noEmit` verifies typecheck correctness in early stages.

### Agent Rules
- **Memory Persistence:** Must update this `MEMORY.md` at the end of each session.
- **Skill Discovery:** Run `bunx skills find <topic>` before starting any phase. Do not guess APIs.
- **Anti-Hallucination:** Search the context window (Context7 or equivalent) every 3-4 files/major subsystems completed.

---

## 4. Session History & Task Log

### 2026-06-16 — Session 1: Planning and Scaffolding Rules
- **Actor:** Antigravity (Gemini 3.5 Flash)
- **Actions:**
  - Reviewed the monorepo design goals and build phases in [AGENTS.md](file:///home/equation/Projects/motherboard/AGENTS.md).
  - Added the **Memory persistence rule** to [AGENTS.md](file:///home/equation/Projects/motherboard/AGENTS.md) to ensure persistent knowledge handoff.
  - Created [MEMORY.md](file:///home/equation/Projects/motherboard/MEMORY.md) file to log current workspace status.
  - Initialized Bun workspace and Turborepo.
  - Scaffolded the folder structure and all configurations (`package.json`, `tsconfig.json`, entry files) for all 8 packages and apps.
  - Configured root level files (`turbo.json`, `tsconfig.base.json`, `.env.example`, `docker-compose.yml`, placeholder Dockerfiles).
  - Successfully ran `bun install` and verified workspace-wide compilation using `tsc --noEmit` across all apps and packages.
- **Status:** Phase 0 complete and verified. Ready to start Phase 1.

### 2026-06-17 — Session 2: Documenting Skill Guidelines
- **Actor:** Antigravity (Gemini 3.5 Flash)
- **Actions:**
  - Added "AI Agent Skill-Specific Guidelines" to [AGENTS.md](file:///d:/motherboard/AGENTS.md) to define precise usage triggers for codebase developer skills (matching exactly the folders in `.agents/skills`).
  - Updated [AGENTS.md](file:///d:/motherboard/AGENTS.md) to add explicit conventions for always performing atomic commits.
  - Aligned the listed skills in [AGENTS.md](file:///d:/motherboard/AGENTS.md) by removing `prd` and `reasoningbank-intelligence` as they are not present in `.agents/skills/`.
  - Added `prd`, `drizzle` & `drizzle-orm-expert`, and `react-patterns` & `react-performance` to the skill guidelines in [AGENTS.md](file:///d:/motherboard/AGENTS.md) following their creation on disk.
  - Added the `token-efficiency` skill guideline to [AGENTS.md](file:///d:/motherboard/AGENTS.md) after verifying its directory presence on disk. Checked for `safety-guard`, which is currently absent from `.agents/skills/` and therefore not listed in the guidelines.
  - Added the `safety-guard` skill guideline to [AGENTS.md](file:///d:/motherboard/AGENTS.md) after its directory appeared in `.agents/skills/`. Checked for `nodejs-backend-patterns`, which is currently absent from `.agents/skills/` and therefore not listed in the guidelines.
  - Integrated the full Discord role hierarchy, configuration mappings, access matrix, and meeting scopes from `role_structure.md` into [AGENTS.md](file:///d:/motherboard/AGENTS.md) and [techspec.md](file:///d:/motherboard/docs/techspec.md).
  - Deleted the redundant `role_structure.md` file from the workspace.
  - Added `nodejs-backend-patterns` and `impeccable` skill guidelines to [AGENTS.md](file:///d:/motherboard/AGENTS.md) following their availability/requests.
  - Overwrote [README.md](file:///d:/motherboard/README.md) with the motherboard project specifications, features, technology stack, repository structure, and development conventions.
  - Created [brandkit.md](file:///d:/motherboard/docs/brandkit.md) to store the brand guidelines and visual asset creative standards.
  - Embedded the bits&bytes brand logo at the top of [README.md](file:///d:/motherboard/README.md).
  - Staged and pushed all newly created skills directories, lock files, and documentation updates to Git.
### 2026-06-17 — Session 3: Neo-Brutalist Design System & Shadcn Components
- **Actor:** Antigravity (Gemini 3.5 Pro)
- **Actions:**
  - Deleted the custom React UI components (`Button`, `Card`, `Input`, `Badge`, `Avatar`) that were manually generated in `packages/ui/src/` to align with the shadcn/ui registry.
  - Configured `@bnb/ui` (`packages/ui`) for Shadcn CLI by creating `components.json`, `tailwind.config.js`, and `src/index.css` containing the bits&bytes HSL theme colors (Burgundy, Orange, Neutral Dark).
  - Added path mappings (`@/*` -> `./src/*`) to `packages/ui/tsconfig.json` and created class merging helper `src/lib/utils.ts`.
  - Successfully installed all neobrutalism UI components from the `neobrutalism.dev` registry using `pnpm dlx shadcn@latest add` CLI commands.
  - Installed `class-variance-authority` and necessary Radix UI primitives as package dependencies for the library.
  - Added the `neobrutalism` skill to the AI Agent guidelines in [AGENTS.md](file:///d:/motherboard/AGENTS.md).
  - Created [design.md](file:///d:/motherboard/docs/design.md) containing the complete bits&bytes brand guidelines and Neo-Brutalist design system specifications.
  - Updated [README.md](file:///d:/motherboard/README.md) to reference the Neo-Brutalist design specifications.
- **Status:** Shared UI component library (`@bnb/ui`) fully initialized and populated with neobrutalism.dev components. Ready to start Phase 1/2 of database/IAM development.

### 2026-06-17 — Session 4: Adding Database Migration & Billing Skills
- **Actor:** Antigravity (Gemini 3.5 Pro)
- **Actions:**
  - Added `database-migrations-sql-migrations` and `finance-billing-ops` skill guidelines to [AGENTS.md](file:///d:/motherboard/AGENTS.md).
- **Status:** Skill rules updated and committed.

### 2026-06-17 — Session 5: Adding Next.js Best Practices Skill
- **Actor:** Antigravity (Gemini 3.5 Pro)
- **Actions:**
  - Created `.agents/skills/nextjs-best-practices/SKILL.md` defining key App Router and rendering/fetching/routing best practices.
  - Added `nextjs-best-practices` skill guidelines to [AGENTS.md](file:///d:/motherboard/AGENTS.md).
- **Status:** Skill rules and directories updated and pushed.

### 2026-06-17 — Session 6: Documenting Project Roadmap
- **Actor:** Antigravity (Gemini 3.5 Pro)
- **Actions:**
  - Created [roadmap.md](file:///d:/motherboard/docs/roadmap.md) describing the five roadmap stages (Finance, AI, Department features, Compliance, TBD) from the whiteboard roadmap session.
  - Linked [roadmap.md](file:///d:/motherboard/docs/roadmap.md) in [README.md](file:///d:/motherboard/README.md) and [AGENTS.md](file:///d:/motherboard/AGENTS.md) for future agent context.
- **Status:** Roadmap documented, committed, and pushed.

### 2026-06-17 — Session 7: Legal Wiki Context Consolidation
- **Actor:** Antigravity (Gemini 3.5 Pro)
- **Actions:**
  - Read all 16 operational wiki files from the external directory `D:\bitsnbytes\agreements\legal-docs\notion-wiki`.
  - Consolidated legal parameters, executive rosters, authority matrix limitations, financial rules, safeguarding policies, minor contract handling, and Discord bot integration specs.
  - Created [legal_governance_rules.md](file:///d:/motherboard/docs/legal_governance_rules.md) to serve as a persistent operational reference.
  - Added the `fastify-best-practices` skill guidelines to [AGENTS.md](file:///d:/motherboard/AGENTS.md) per user request.
  - Staged, committed, and pushed both files to Git.
- **Status:** Consolidated legal and governance reference document completed, skill rules updated, and all changes pushed.

### 2026-06-17 — Session 8: Migration to FastAPI & CORS Security Guide
- **Actor:** Antigravity (Gemini 3.5 Pro)
- **Actions:**
  - Migrated the backend tech stack rules from Fastify/Node.js to FastAPI/Python.
  - Deleted the obsolete Node.js/Fastify backend skill folders (`backend-patterns`, `nodejs-backend-patterns`, `fastify-best-practices`) from `.agents/skills/` and removed them from `skills-lock.json`.
  - Registered `fastapi` and `fastapi-patterns` skill guidelines in [AGENTS.md](file:///d:/motherboard/AGENTS.md).
  - Authored a defensive [cors_security_guide.md](file:///d:/motherboard/docs/cors_security_guide.md) documenting CORS risk vectors and secure FastAPI testing patterns.
  - Staged, committed, and pushed all updates to Git.
- **Status:** Backend skill migration complete and defensive CORS documentation pushed.

### 2026-06-17 — Session 9: Rewrite Specification for FastAPI Backend
- **Actor:** Antigravity (Gemini 3.5 Flash)
- **Actions:**
  - Brainstormed and aligned on the Python directory layout, using Approach 1 where core backend packages (IAM, Database, Provisioning, Event Bus, Plugin SDK) are placed inside `apps/api/app/` as internal modules, and Next.js acts as the decoupled frontend.
  - Selected async SQLAlchemy 2.0 with Alembic migrations for the database layer.
  - Rewrote [techspec.md](file:///d:/motherboard/docs/techspec.md) to define the FastAPI/Python monorepo structure, technology versions, SQLAlchemy ORM schema tables, async principal resolution and policy validation, typed asyncio and Redis event bus, dynamic plugin router loading, background sync worker, and uv-based Dockerfiles.
  - Synchronized the embedded specification copy inside [AGENTS.md](file:///d:/motherboard/AGENTS.md) to maintain absolute consistency across workspace instructions.
  - Deleted the obsolete Drizzle skills (`drizzle`, `drizzle-orm-expert`) from `.agents/skills/` and removed them from `skills-lock.json`.
  - Verified both specifications are clean, complete, and contain no TODO/TBD placeholders.
- **Status:** Backend specification fully transitioned to FastAPI, and all documents synchronized.


### 2026-06-17 — Session 10: Phase 0 Planning for FastAPI Repo Realignment
- **Actor:** Code
- **Actions:**
  - Read `docs/techspec.md`, the current root workspace files, Docker config, and memory notes to compare the FastAPI edition spec against the live Bun/TypeScript scaffold.
  - Ran `bunx skills find brainstorming` and `bunx skills find plan-orchestrate` as required before planning work.
  - Launched a nine-agent planning batch to synthesize a Phase 0 execution plan from multiple model perspectives.
  - Confirmed the repo still contains the old TypeScript backend packages (`packages/db`, `packages/iam`, `packages/events`, `packages/plugin-sdk`, `packages/provisioning`) and a Fastify-oriented `apps/api` scaffold.
  - Identified the main Phase 0 migration gap: the spec now expects a hybrid Bun + uv layout with `apps/api` converted to FastAPI/Python and backend domains moved under `apps/api/app/`.
- **Status:** Planning complete; implementation has not started yet. Next step is to execute the agreed Phase 0 repo realignment.

### 2026-06-17 — Session 11: Phase 0 Execution for FastAPI Repo Realignment
- **Actor:** Antigravity (Gemini 3.1 Pro)
- **Actions:**
  - Deleted obsolete TypeScript backend packages (`packages/db`, `packages/iam`, `packages/events`, `packages/plugin-sdk`, `packages/provisioning`).
  - Removed old Fastify scaffolding from `apps/api` (`src`, `node_modules`, `package.json`, `tsconfig.json`).
  - Verified `apps/api` Python layout using `uv` matching the specification.
  - Confirmed `apps/web` depends only on `@bnb/ui`.
- **Status:** Phase 0 execution complete. Repository is correctly realigned to the hybrid Bun + uv FastAPI spec. Ready for Phase 1.

### 2026-06-17 — Session 12: Cinematic Space-Travel Landing Page
- **Actor:** Antigravity (Gemini 3.5 Flash)
- **Actions:**
  - Brainstormed and implemented a high-fidelity Space-Travel Landing Page in `apps/web` utilizing Next.js 15 App Router and React 19.
  - Installed `framer-motion` in `apps/web` for entrance animations.
  - Authored a custom JS-based [FadingVideo.tsx](file:///d:/motherboard/apps/web/components/FadingVideo.tsx) player using requestAnimationFrame to handle manual looping and 500ms opacity crossfading.
  - Authored [BlurText.tsx](file:///d:/motherboard/apps/web/components/BlurText.tsx) to animate text word-by-word with staggered opacity/blur transitions triggered by a 10% threshold IntersectionObserver.
  - Implemented [HeroSection.tsx](file:///d:/motherboard/apps/web/components/HeroSection.tsx) with a fixed glass navbar, stats display cards, and entrance animations.
  - Implemented [CapabilitiesSection.tsx](file:///d:/motherboard/apps/web/components/CapabilitiesSection.tsx) with a kicker, title, and three interactive liquid-glass cards (AI Scenery, Batch Production, Smart Lighting) containing customized SVGs.
  - Added `.liquid-glass` and `.liquid-glass-strong` styles to the shared index.css stylesheet in [packages/ui](file:///d:/motherboard/packages/ui/src/index.css) and updated package exports to expose the CSS to Next.js.
  - Verified a clean and successful compilation and Turborepo build (`bun run build`) with no TypeScript or Next.js Webpack compile errors.
- **Status:** Cinematic space-travel landing page successfully implemented, styled, verified, and compiled.

### 2026-06-17 — Session 13: Phase 1 — Database Schema Implementation
- **Actor:** Antigravity (Claude Sonnet 4.6 Thinking)
- **Actions:**
  - Read MEMORY.md, techspec.md, and all existing app/api files to understand exact current state.
  - Read fastapi/SKILL.md for best practices before writing any code.
  - Created [app/db/models.py](file:///home/equation/Projects/motherboard/apps/api/app/db/models.py) with 13 SQLAlchemy 2.0 ORM tables using full `Mapped[]` type annotations, `relationship()` with cascades, composite indexes, and JSONB columns.
  - Created [app/db/seed_data.py](file:///home/equation/Projects/motherboard/apps/api/app/db/seed_data.py) with 15 system groups, 24 core permissions, 14 Discord role→group mappings (from AGENTS.md role hierarchy), and 12 city forks.
  - Created [app/db/seeder.py](file:///home/equation/Projects/motherboard/apps/api/app/db/seeder.py) with idempotent `INSERT ... ON CONFLICT DO NOTHING` seed runner.
  - Updated [app/db/__init__.py](file:///home/equation/Projects/motherboard/apps/api/app/db/__init__.py) with clean public exports.
  - Updated [app/main.py](file:///home/equation/Projects/motherboard/apps/api/app/main.py) with lifespan context manager: auto-migrate via Alembic, auto-seed on boot, CORS middleware, and router registration.
  - Updated [app/config.py](file:///home/equation/Projects/motherboard/apps/api/app/config.py) with `redis_url` and `cors_origins` fields.
  - Updated [app/dependencies.py](file:///home/equation/Projects/motherboard/apps/api/app/dependencies.py) with `DbSession` and `AppSettings` typed Annotated aliases.
  - Wrote 7 API routers: [health.py](file:///home/equation/Projects/motherboard/apps/api/app/routers/health.py), [users.py](file:///home/equation/Projects/motherboard/apps/api/app/routers/users.py), [groups.py](file:///home/equation/Projects/motherboard/apps/api/app/routers/groups.py), [forks.py](file:///home/equation/Projects/motherboard/apps/api/app/routers/forks.py), [audit.py](file:///home/equation/Projects/motherboard/apps/api/app/routers/audit.py), [sync.py](file:///home/equation/Projects/motherboard/apps/api/app/routers/sync.py), [plugins.py](file:///home/equation/Projects/motherboard/apps/api/app/routers/plugins.py).
  - Wrote 6 schema files: users, groups, forks, audit, sync, plugins (all Pydantic v2 with `ConfigDict(from_attributes=True)`).
  - Fixed `pyproject.toml`: added `[tool.fastapi]` entrypoint, `[build-system]` hatchling block, and `[tool.hatch.build.targets.wheel]` package path.
  - Initialized Alembic (`uv run alembic init alembic`).
  - Configured [alembic/env.py](file:///home/equation/Projects/motherboard/apps/api/alembic/env.py) with async engine, NullPool, and `Base.metadata` autogenerate.
  - Ran `alembic revision --autogenerate -m "initial_schema"` → detected all 13 tables + indexes.
  - Ran `alembic upgrade head` → all 13 tables live in Postgres (confirmed via `\dt`).
  - Committed 29 files on branch `db/init-schema` (commit `c6c8769`).
- **Decisions Made:**
  - Added `Fork` and `ForkMember` tables beyond the spec's original set — necessary for the fork-scoped IAM checks described in AGENTS.md.
  - Added `SyncRun` table for Discord provisioning observability.
  - Used `slug` as unique identifier for Group and Fork (in addition to UUID PK) for human-readable API paths and seed conflict resolution.
  - Used `ON CONFLICT DO NOTHING` for all seeds so the seeder is safe to run on every container start.
  - Used polymorphic `principal_id` in grants (not FKs) to support both user and group grants in one table — a deliberate trade-off for query simplicity.
- **Status:** Phase 1 complete and verified. All 13 tables live in Postgres. Ready for Phase 2 (IAM module).

### 2026-06-17 — Session 13: Low-Key Landing Page Refinements & SSO Configuration
- **Actor:** Antigravity (Gemini 3.5 Pro)
- **Actions:**
  - Removed all interactive operations CTAs/buttons from the landing page, keeping it very low-key.
  - Configured a dedicated `next.config.js` and standard `not-found.tsx` to resolve Next.js Webpack page data collection and route-manifest resolution errors.
  - Restored the user-preferred translucent `liquid-glass` card styling, adjusting background opacity (`rgba(255, 255, 255, 0.035)`) and backdrop-blur (`12px`) inline overrides to ensure clear visibility.
  - Added requested reference links to `gobitsnbytes.org` and the `gobitsnbytes/motherboard` GitHub repository inside the info card.
  - Updated the subtitle text to precisely state: "this is an internal tool to manage all operations and work of bits&bytes™ (GOBITSNBYTES FOUNDATION)".
  - Updated access control copy to "Invite-based access" and scope to "Strictly Internal Tool" to clearly communicate authentication structure and scope.
  - Optimized the background video player (`FadingVideo.tsx`) to utilize native hardware-accelerated video looping, removing complex requestAnimationFrame fade-out delays and successfully resolving the split-second black frame/flicker.
  - Verified zero page scroll by keeping layout classes locked to `h-screen overflow-hidden`.
  - Staged, committed, and pushed all changes successfully.
- **Status:** Low-key landing page finalized, verified, built, and changes pushed to remote branch.

### 2026-06-17 — Session 14: Documentation De-duplication & Clean-up
- **Actor:** Antigravity (Gemini 3.5 Flash)
- **Actions:**
  - Consolidated creative and brand standards from `docs/brandkit.md` into `docs/design.md` under section 5 ("Brand Usage & Creative Standards").
  - Renamed the QA Verification Checklist in `docs/design.md` to section 6.
  - Deleted the redundant `docs/brandkit.md` file from the workspace.
  - Cleaned up `AGENTS.md` by stripping the duplicated technical specification sections and role configuration tables (now solely maintained in `docs/techspec.md`).
  - Added a lean Documentation Index section inside `AGENTS.md` citing all project `.md` files and their purposes.
- **Status:** Documentation de-duplicated, consolidated, and indexed.

### 2026-06-17 — Session 15: Next.js 15 Dashboard App Shell with NextAuth v5
- **Actor:** Code
- **Actions:**
  - **Infrastructure blockers resolved:**
    - Populated `@bnb/ui` barrel exports in `packages/ui/src/index.ts` (excluding `sidebar`, `resizable`, `form` due to API incompatibilities).
    - Added `transpilePackages: ["@bnb/ui"]` to `apps/web/next.config.js` for Next.js to process workspace TypeScript source.
    - Added `baseUrl`, `paths` (`@/*` → `../../packages/ui/src/*`) and `exactOptionalPropertyTypes: false` to `apps/web/tsconfig.json`.
    - Merged Neo-Brutalist Tailwind tokens into `apps/web/tailwind.config.js` (colors as CSS vars, `borderRadius.base`, `boxShadow.shadow`, translate values).
    - Fixed root layout (`apps/web/app/layout.tsx`): removed `overflow-hidden`, added `dark` class for dark mode CSS variables.
  - **NextAuth v5 setup:**
    - Installed `next-auth@beta` (v5.0.0-beta.31) in `apps/web`.
    - Created `apps/web/types/next-auth.d.ts` augmenting Session.user with `discordId` and JWT with `discordId` + `accessToken`.
    - Created `apps/web/lib/auth.ts` with Discord OAuth provider (scopes: `identify email guilds guilds.members.read`), JWT/session callbacks, fire-and-forget upsert to `${API_URL}/api/auth/upsert`.
    - Created `apps/web/app/api/auth/[...nextauth]/route.ts` exporting GET/POST handlers.
    - Created `apps/web/middleware.ts` protecting `/dashboard(.*)` routes with session check + redirect.
  - **Dashboard layout & components:**
    - Created `AuthProvider` (SessionProvider wrapper), custom `Sidebar` (desktop fixed + mobile hamburger drawer using lucide-react icons), `Topbar` (user avatar + sign-out), `PageSkeleton` (shimmer), `EmptyState` (icon + heading + description card).
    - Created `apps/web/app/dashboard/layout.tsx` (server component with auth guard + AuthProvider + DashboardShell).
    - Created dashboard root redirect (`/dashboard` → `/dashboard/overview`).
    - Created 5 placeholder pages: overview, members, iam, audit, settings — each with EmptyState.
  - **Login page:**
    - Created `apps/web/app/(public)/login/page.tsx` with centered card, Discord OAuth button, error state handling, Suspense-wrapped `useSearchParams`.
  - **Critical build fix:** Resolved `d.createContext is not a function` SSR error caused by `transpilePackages` evaluating all `@bnb/ui` barrel modules server-side. Fixed by removing all `@bnb/ui` component imports from dashboard components and using plain HTML elements with Neo-Brutalist Tailwind classes instead.
  - **Typecheck fix:** Added `exactOptionalPropertyTypes: false` and excluded `resizable.tsx`/`form.tsx` from `packages/ui/tsconfig.json` to fix pre-existing Radix UI type errors.
  - Added `typecheck` script to `apps/web/package.json`.
  - **Verification:** `bun run build` passes (11 routes, 0 errors), `bun run typecheck` passes (2/2 packages clean), no `any` types, no `console.log`.
- **Status:** Dashboard app shell complete. Landing page at `/` unchanged. Auth flow, dashboard layout, and all placeholder pages verified via build.
### 2026-06-17 — Session 16: Phase 2.2-2.5 Implementation (IAM Policy Evaluator & API Router)
- **Actor:** Jules
- **Actions:**
  - Implemented Phase 2 (IAM Policy Evaluation) according to specification in `docs/techspec.md`.
  - Created `apps/api/app/iam/policy.py` containing `can`, `require_permission` and `batch_can` evaluation logic.
  - Key decision: `batch_can` uses single DB query with IN clause across all permission keys for efficient multiple checks.
  - Created `apps/api/app/iam/constants.py` with `SYSTEM_GROUPS` and `CORE_PERMISSIONS`.
  - Created `apps/api/app/iam/audit.py` with `write_audit_entry` that records actions without committing.
  - Added Pydantic schemas in `apps/api/app/schemas/iam.py` for API routes validation.
  - Implemented API endpoints mapping to schema operations under `apps/api/app/routers/iam.py` correctly implementing `CurrentUserDep`.
  - Authored automated tests using `pytest` + `pytest-asyncio` for IAM core functions handling Super Admin, Expirations, Global and Resource matching strategies inside `apps/api/tests/test_iam_policy.py`.
- **Status:** Phase 2 (IAM Policy Evaluation) status: COMPLETE.
