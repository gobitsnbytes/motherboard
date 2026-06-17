# Motherboard Operations Platform — Agent Memory

This file serves as a persistent, running log of all tasks performed, design decisions made, technical challenges resolved, and current workspace status. Every agent invocation updates this document to ensure perfect continuity across sessions.

---

## 1. Project Status Overview

- **Current Phase:** Phase 1 (Database Schema `@bnb/db`)
- **Next Milestone:** Define Drizzle ORM Tables & Run Initial Migrations

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
- [ ] **Phase 1: Database Schema (`@bnb/db`)**
  - [ ] Install dependencies (`drizzle-orm`, `postgres`, `drizzle-kit`)
  - [ ] Define database tables (users, discord-accounts, groups, memberships, role mappings, permissions, grants, delegations, audit log, plugin registry)
  - [ ] Configure `drizzle.config.ts`
  - [ ] Implement database client singleton (`src/client.ts`)
  - [ ] Generate and run initial migrations (`bunx drizzle-kit generate` & `migrate`)
- [ ] **Phase 2: IAM Package (`@bnb/iam`)**
- [ ] **Phase 3: Event Bus (`@bnb/events`)**
- [ ] **Phase 4: Plugin SDK (`@bnb/plugin-sdk`)**
- [ ] **Phase 5: Provisioning Worker (`@bnb/provisioning`)**
- [ ] **Phase 6: Shared UI Component Library (`@bnb/ui`)**
- [ ] **Phase 7: Fastify Core API (`apps/api`)**
- [ ] **Phase 8: Web Dashboard (`apps/web`)**
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

