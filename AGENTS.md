# bnb-motherboard — Agent Build Instructions

> **Before starting any phase:** Run `bunx skills find <topic>` to locate relevant skill documentation for the task at hand (e.g. `bunx skills find drizzle orm`, `bunx skills find fastify plugins`, `bunx skills find nextjs app router`, `bunx skills find discord oauth`). Use the output to guide implementation — do not guess at APIs.
>
> **Anti-hallucination rule:** After every 3–4 files created or every major subsystem completed, stop and search your context window (context 7 or equivalent) for the latest state of relevant interfaces, schemas, and type contracts before continuing. Write code against what actually exists in the codebase, not against memory.
>
> **Memory persistence rule:** Every agent invocation must document tasks completed, decisions made, codebase insights, and current progress in [MEMORY.md](file:///home/equation/Projects/motherboard/MEMORY.md). Update this file at the end of each session or major step so that future agents have a continuous record of the project's evolution.
>
> **AI Agent Skill-Specific Guidelines:**
> - **`brainstorming`**: MUST use this before any creative work - creating features, building components, adding functionality, or modifying behavior. Explores user intent, requirements, and design before implementation.
> - **`prd`**: Generate high-quality Product Requirements Documents (PRDs) for software systems and AI-powered features. Includes executive summaries, user stories, technical specifications, and risk analysis.
> - **`ui-ux-pro-max`**: MUST use this before any UI/UX work (layouts, styling, animations, product types, guidelines).
> - **`impeccable`**: Use when the user wants to design, redesign, shape, critique, audit, polish, clarify, distill, harden, optimize, adapt, animate, colorize, extract, or otherwise improve a frontend interface (covers UX review, visual hierarchy, cognitive load, accessibility, micro-interactions, responsive behavior, theming, design systems/tokens, etc. Not for backend-only tasks).
> - **`neobrutalism`**: Use when designing or implementing user interfaces with the neobrutalist aesthetic, including bold borders, custom hard shadows, high-contrast layouts, and brandkit integrations.
> - **`code-reviewer`**: MUST use this skill towards the end of every task, and always before a push. Always perform atomic commits.
> - **`backend-patterns` & `nodejs-backend-patterns`**: MUST use for all backend work (creating Fastify/Express servers, REST/GraphQL APIs, middleware, error handling, authentication, database integration, and microservices).
> - **`frontend-patterns`**: MUST use for all frontend/UI work.
> - **`drizzle` & `drizzle-orm-expert`**: MUST use when building type-safe database layers with Drizzle (schema design, relational queries, migrations, indexes, joins, inferred types, db.select/db.query, and pgTable patterns).
> - **`database-migrations-sql-migrations`**: SQL database migrations with zero-downtime strategies for PostgreSQL, MySQL, and SQL Server. Focus on data integrity and rollback plans.
> - **`react-patterns` & `react-performance`**: MUST use when writing, reviewing, or refactoring React/Next.js components for styling, hooks discipline, server/client boundaries, and performance optimization.
> - **`finance-billing-ops`**: Evidence-first revenue, pricing, refunds, team-billing, and billing-model truth workflow for ECC. Use when the user wants a sales snapshot, pricing comparison, duplicate-charge diagnosis, or code-backed billing reality instead of generic payments advice.
> - **`memory-md-management`**: Use when checking, auditing, updating, improving, or maintaining project memory files (such as `MEMORY.md`, `CLAUDE.md`, or creating one).
> - **`deployment-patterns` & `devops-rollout-plan`**: MUST use for all DevOps, Docker, CI/CD, rollout plans, and rollback/deployment strategy work.
> - **`security-review`**: MUST use when adding authentication, handling user input, working with secrets, creating API endpoints, or implementing sensitive features.
> - **`token-efficiency`**: Use to reduce token waste by 40-60% through anti-sycophancy rules, tool-call budgets, one-pass coding, task profiles, and read-before-write enforcement.
> - **`humaniser`**: Use while writing basically anything to remove signs of AI-generated writing and ensure natural phrasing.
> - **`ai-agent-development`**: Use for all AI agent work (CrewAI, LangGraph, custom agents).
> - **`vibe-code-cleanup` & `vibe-code-auditor`**: Use at all times for security and hardening once a task is done.
> - **`safety-guard`**: Use when working on production systems or running agents autonomously to prevent destructive operations.
> - **`plan-orchestrate`**: Use/suggest always for multi-step plan development.

***

## What Is Being Built

**bnb-motherboard** is the internal operations platform for the bits&bytes network. It serves as:

- An **Identity & Access Management (IAM) core** — Discord is the upstream identity provider. Users log in via Discord OAuth. Discord guild roles are imported via the Discord API and mapped to internal groups through an admin UI.
- A **provisioning engine** — a sync worker keeps internal users, roles, and entitlements in sync with the Discord guild on a schedule and on-demand.
- A **plugin platform** — an elaborately specified SDK allows first- and third-party plugins to register routes, UI panels (using the main app's component library), event bus subscriptions, database migrations, permissions, and audit entries.
- A **web dashboard** — Next.js frontend decoupled from the Fastify backend via a clean REST API boundary.
- A **Discord bot integration layer** — the existing bits&bytes Discord bot connects to the motherboard over HTTP/WebSocket to sync identity state. The bot is NOT rebuilt here; only the integration contract is defined and the sync endpoint is implemented.

All services run in Docker containers orchestrated with Docker Compose for self-hosted VPS deployment.

***

## Required Secrets — Gather Before Starting

The agent must not proceed to Phase 2 until the operator confirms all of the following are available as environment variables. Create a `.env.example` at the repo root and document every variable.

| Variable | Description | Where to get it |
|---|---|---|
| `DISCORD_CLIENT_ID` | OAuth2 app client ID | Discord Developer Portal → OAuth2 |
| `DISCORD_CLIENT_SECRET` | OAuth2 app client secret | Discord Developer Portal → OAuth2 |
| `DISCORD_BOT_TOKEN` | Bot token for guild member/role sync | Discord Developer Portal → Bot |
| `DISCORD_GUILD_ID` | The bits&bytes Discord server ID | Right-click server → Copy Server ID |
| `DATABASE_URL` | Postgres connection string | Self-hosted container (auto-generated in docker-compose) |
| `SESSION_SECRET` | Long random string for cookie signing | Generate: `openssl rand -hex 64` |
| `API_INTERNAL_SECRET` | Shared secret between API and Bot | Generate: `openssl rand -hex 32` |
| `NEXTAUTH_SECRET` | NextAuth.js secret | Generate: `openssl rand -hex 32` |
| `NEXTAUTH_URL` | Public URL of the Next.js app | VPS domain or `http://localhost:3000` |
| `API_URL` | Internal URL of Fastify API | `http://api:4000` in Docker, `http://localhost:4000` locally |

**Discord OAuth redirect URI** to register in the Developer Portal:
- `http://localhost:3000/api/auth/callback/discord` (development)
- `https://<your-domain>/api/auth/callback/discord` (production)

***

## Monorepo Structure

```
bnb-motherboard/
├── apps/
│   ├── web/                    # Next.js 15 App Router (frontend)
│   └── api/                    # Fastify 5 backend
├── packages/
│   ├── db/                     # Drizzle ORM schema + migrations + client
│   ├── iam/                    # Principal resolution, policy evaluator, permission helpers
│   ├── provisioning/           # Discord sync worker, role mapper, deprovisioner
│   ├── events/                 # Typed event bus (internal, in-process + Redis pub/sub)
│   ├── plugin-sdk/             # Plugin development kit — the elaborated SDK
│   └── ui/                     # Shared React component library (used by web + plugin UIs)
├── plugins/                    # First-party plugins (empty in Phase 1, populated in Phase 3+)
├── docker/
│   ├── api.Dockerfile
│   ├── web.Dockerfile
│   └── worker.Dockerfile
├── docker-compose.yml
├── docker-compose.prod.yml
├── .env.example
├── .env                        # gitignored
├── turbo.json
├── package.json                # Bun workspace root
└── AGENTS.md                   # This file, to be kept updated
```

**Naming conventions:**
- All packages use `@bnb/` scope (e.g. `@bnb/db`, `@bnb/iam`, `@bnb/plugin-sdk`).
- File names: `kebab-case` for all files and directories.
- TypeScript: strict mode everywhere, no `any` — use `unknown` and narrow.
- Exports: each package has a single `src/index.ts` barrel export.
- No barrel re-export chains deeper than one level.

***

## Technology Versions (verify with `bunx skills find` before pinning)

| Layer | Technology |
|---|---|
| Runtime | Bun (latest stable) |
| Monorepo | Bun workspaces + Turborepo |
| Frontend | Next.js 15 App Router, React 19, TypeScript |
| Backend | Fastify 5, TypeScript |
| Database | PostgreSQL 16 (Docker container) |
| ORM | Drizzle ORM + drizzle-kit |
| Auth (web) | NextAuth.js v5 (Auth.js) with Discord provider |
| Auth (API) | Fastify session + JWT for API-to-API |
| Bot integration | HTTP contract only (existing discord.js bot calls the API) |
| Event bus | EventEmitter (in-process) + optional Redis pub/sub (same Redis container) |
| Containerization | Docker + Docker Compose |
| Component library | Radix UI primitives + Tailwind CSS (shared via `@bnb/ui`) |

***

## Discord Role Hierarchy & Access Control

This section defines the structured role hierarchy, permission system, and Discord Role IDs implemented across the Bits&Bytes Discord Bot and Notion integration.

### Visual Role Hierarchy Diagram

```mermaid
graph TD
    %% Global Admins
    subgraph Global Administration
        admin["Administrator / Owner<br/>ID: 1480620981587279993"]
        exec["Executive Leadership / HQ Role<br/>(Full Access to All Forks)<br/>IDs: 1506019032015310949, 1509256369994203146"]
        dept["Department Lead Role<br/>(Full Access to All Forks)<br/>ID: 1506323726223016149"]
    end

    %% Global Contributors
    subgraph Global Contributors / Parent Tracks
        contrib["@Contributor Role<br/>(General Access)<br/>ID: 1506019068132462804"]
        track["Global Track Roles<br/>(tech, creative, ops, outreach)<br/>(Cross-Fork VIEW Access Only)"]
    end

    %% Fork Local Levels
    subgraph Local Fork Level (City-Specific)
        city["City Role (e.g., delhi)<br/>(Community Level)"]
        cityContrib["Contributor City Role (e.g., contributor-delhi)<br/>(Fork Member Access)"]
        
        subgraph Local Hierarchy (Requires @Contributor + City + Contributor City)
            forkLead["Fork Lead / @fork-lead<br/>(Full City-Level Modify/View)<br/>ID: 1490410901147488286"]
            localTrack["Fork Track Lead Roles<br/>(tech-lead, creative-lead, ops-lead, outreach-lead)<br/>(Modify Specific Track Only)<br/>IDs: 1509224755595841676, 1509224757579616276, 1509224760293195927, 1509224762906247178"]
            forkContrib["Fork Contributor<br/>(City-Specific VIEW Only)"]
        end
    end

    %% Connectors
    admin --> exec
    exec --> dept
    dept --> contrib
    contrib --> track
    contrib --> cityContrib
    city --> cityContrib
    
    %% Fork roles need the intersection
    cityContrib --> forkLead
    cityContrib --> localTrack
    cityContrib --> forkContrib
```

### Core Role Configuration Mapping

#### 1. Global Administrative Roles (HQ & Staff)
These roles hold full, global permissions to read and modify all server resources, Notion data, and bot configurations.

| Role Name | Discord Role ID | Color (Hex) | Hoisted | Primary Purpose / How Assigned |
| :--- | :--- | :--- | :--- | :--- |
| `admin` | `1480620981587279993` | `#f1c40f` (Gold) | No | **Administrator**: Full server and guild owner status. |
| `Executive Leadership` | `1506019032015310949` | `#97192c` (Burgundy) | Yes | **Executive Team**: Full server and database operations control. |
| `Department Leads` | `1506323726223016149` | `#fc920d` (Orange) | Yes | **Global Track Leadership**: Oversight of all organization tracks. |
| `hq` | `1509256369994203146` | `#f1c40f` (Gold) | Yes | **Foundation Core**: Manually assigned to Bits&Bytes Foundation members. |

#### 2. Fork Track Lead Roles
These roles represent the track leads of individual city forks (e.g., Bangalore Tech Lead, Delhi Ops Lead). The bot automatically assigns these roles to fork members based on their Notion role.

| Role Name | Discord Role ID | Color (Hex) | Hoisted | Primary Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `tech-lead` (or `Tech Lead`) | `1509224755595841676` | `#1f8b4c` (Emerald Green) | Yes | **Tech Lead**: Leads the tech track inside their city fork. |
| `creative-lead` (or `Creative Lead`) | `1509224757579616276` | `#ad1457` (Magenta) | Yes | **Creative Lead**: Leads the creative/design track inside their city fork. |
| `ops-lead` (or `Ops Lead`) | `1509224760293195927` | `#11806a` (Teal) | Yes | **Ops Lead**: Leads the operations track inside their city fork. |
| `outreach-lead` (or `Outreach Lead`) | `1509224762906247178` | `#a84300` (Orange/Rust) | Yes | **Outreach Lead**: Leads the outreach track inside their city fork. Also acts as a Global Department Lead. |

#### 3. Base Contributor & Global Track Roles
These roles represent base membership and global track-specific capabilities without local city restrictions.

| Role Name | Discord Role ID | Color (Hex) | Hoisted | Primary Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `Contributor` | `1506019068132462804` | `#00ff94` (Bright Green) | Yes | **Base Contributor**: Auto-granted to all onboarded members. |
| `Builder` | `1480624226414366924` | `#3498db` (Light Blue) | Yes | **Legacy/General Contributor**: Builder role mapping. |
| `tech` | `1509224750663073865` | `#3498db` (Blue) | Yes | **Global Tech Contributor**: General parent developer track. |
| `creative` | `1490412912420847646` | `#eb459e` (Pink) | No | **Global Creative Contributor**: General parent design track. |
| `ops` | `1490413018830471332` | `#eb459e` (Pink) | No | **Global Ops Contributor**: General parent operations track. |
| `outreach` | `1509224752747909351` | `#e67e22` (Orange) | Yes | **Global Outreach Contributor**: General parent outreach track. |

#### 4. Local Fork Lead Roles
These roles manage single city forks (e.g. Delhi, Mumbai, Bangalore).

| Role Name | Discord Role ID | Color (Hex) | Hoisted | Primary Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `fork-lead` | `1490410901147488286` | `#7289da` (Blurple) | Yes | **City Fork Lead**: Leading a city fork. |

#### 5. Local Fork Contributor Identity Roles
These roles are assigned to identify contributors mapped to specific city forks.

| Role Name | Discord Role ID | Color (Hex) | Hoisted | Primary Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `contributor-Bangalore` | `1508766945091260436` | `#000000` | No | Contributor identity for Bangalore. |
| `contributor-Hyderabad` | `1508767008660000840` | `#000000` | No | Contributor identity for Hyderabad. |
| `contributor-Noida` | `1508767019745677394` | `#000000` | No | Contributor identity for Noida. |
| `contributor-Kolkata` | `1508767029593899160` | `#000000` | No | Contributor identity for Kolkata. |
| `contributor-Jaipur` | `1508767044567306310` | `#000000` | No | Contributor identity for Jaipur. |
| `contributor-Solan` | `1508767065308135525` | `#000000` | No | Contributor identity for Solan. |
| `contributor-Beawar` | `1508767089081450587` | `#000000` | No | Contributor identity for Beawar. |

#### 6. Local City Roles (Community Members)
These roles are public/community identity roles for members belonging to specific cities.

| Role Name | Discord Role ID | Color (Hex) | Hoisted | Primary Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `delhi` | `1490411548752085094` | `#5865f2` | No | Delhi community role. |
| `mumbai` | `1490411614292283552` | `#5865f2` | No | Mumbai community role. |
| `chennai` | `1490411705983832325` | `#5865f2` | No | Chennai community role. |
| `kanpur` | `1490411774472753198` | `#5865f2` | No | Kanpur community role. |
| `other-city` | `1490411854189822112` | `#000000` | No | Generic fallback city role. |
| `lucknow` | `1490411988902477824` | `#000000` | No | Lucknow community role. |
| `bangalore` | `1490412532152930315` | `#5865f2` | No | Bangalore community role. |
| `hyderabad` | `1490412746951626752` | `#5865f2` | No | Hyderabad community role. |
| `kolkata` | `1490413148543385822` | `#5865f2` | No | Kolkata community role. |
| `Noida` | `1508052355579641856` | `#000000` | No | Noida community role. |
| `Jaipur` | `1508052382229987470` | `#000000` | No | Jaipur community role. |
| `Solan` | `1508052399338688613` | `#000000` | No | Solan community role. |
| `Beawar` | `1508052414215749683` | `#000000` | No | Beawar community role. |
| `"your-city-name"` | `1508199356077965424` | `#000000` | No | Template city role (hyphenated). |
| `"your city name"` | `1508199867372015616` | `#000000` | No | Template city role (spaced). |
| `example` | `1508200326648565794` | `#000000` | No | Example city role. |

#### 7. Managed & Integration Roles
These roles are managed directly by integrations or external bots, and cannot be modified by other roles.

| Role Name | Discord Role ID | Color (Hex) | Hoisted | Primary Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `Bits&Bytes` (Bot integration) | `1490425472570495210` | `#71368a` | Yes | Primary Bot execution identity role. |
| `Wick` | `1480633459864240264` | `#000000` | No | Wick Security Bot integration role. |
| `AutoMod` | `1480624666610766101` | `#000000` | No | Discord AutoMod system role. |
| `DISBOARD.org` | `1505612966291177492` | `#000000` | No | Disboard bump bot integration. |
| `carl-bot` | `1505995557699584192` | `#000000` | No | Carl-bot helper integration. |
| `Embed Generator` | `1506005487936864288` | `#000000` | No | Embed generator bot integration. |
| `Logger` | `1506019693272502585` | `#000000` | No | Logging bot integration. |
| `Bits&Bytes` (Instance B) | `1510233907008901183` | `#000000` | No | Secondary instance integration. |
| `Bits&Bytes` (Instance C) | `1510234383020458004` | `#000000` | No | Tertiary instance integration. |

#### 8. Miscellaneous / Low Roles

| Role Name | Discord Role ID | Color (Hex) | Hoisted | Primary Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `[Nerds]` | `1480637320699973807` | `#e74c3c` (Red) | Yes | Community badge role. |
| `Quarantine` | `1480633565510369332` | `#b38844` | No | Security quarantine role. |
| `research` | `1490413663239278592` | `#eb459e` | No | Research track role. |
| `muted` | `1490816011727933622` | `#f4424b` | No | Text/voice muted role. |
| `Discord Maintainer` | `1506341723964571868` | `#000000` | No | Server helper role. |
| `dev` | `1510220403573002240` | `#000000` | No | Development testing role. |

### Granular Access Control & Permissions Matrix

The authentication engine evaluates command permissions and Notion access rules through nested logic gates.

#### 1. Global Admins (HQ, Executive Leadership, Staff)
*   **Identification**: Holds Server Admin permissions, `STAFF_ROLE_IDS`, or name matching (`hq`, `Executive Leadership`, `staff`).
*   **Permissions**:
    *   **Full Access**: Implicit read and write (modify) privileges across all forks, Notion databases, meetings, and configurations.
    *   **Bypasses All Scoping**: Automatically passes `isAuthorizedForCity` and `isAuthorizedForForkId` gates.

#### 2. Department Leads (Global Track Leads)
*   **Identification**: Holds the `outreach-lead`, `tech-lead`, `creative-lead`, or `ops-lead` roles.
*   **Permissions**:
    *   **Cross-Fork Control**: Treated as Global Admins for execution purposes.
    *   **Full Access**: Bypasses local city checks, allowing view & modification of all fork pages and event structures.

#### 3. Parent Track Contributors
*   **Identification**: Holds the `@Contributor` role + a global track role (e.g., `tech`, `ops`, `creative`, `outreach`) but **does not** hold any local `contributor-{city}` role.
*   **Permissions**:
    *   **Cross-Fork VIEW Access**: Authorized to *view* the dashboard, health scores, and metrics of any city fork.
    *   **No Modify Privileges**: Cannot create events, submit reports, or modify fork status.

#### 4. Fork Leads
*   **Identification**: Meets Local Fork Member requirements + holds the `Fork Lead` role (or designated as lead in the Notion registry).
*   **Permissions**:
    *   **Full Local Control**: Full read and write (modify) access to any data associated with their specific city fork.
    *   **No Cross-Fork Access**: Cannot view or modify private data from other city forks.

#### 5. Local Track Leads (Fork Department Leads)
*   **Identification**: Meets Local Fork Member requirements + holds a track lead role (e.g. `tech-lead` / `Tech Lead`, `creative-lead` / `Creative Lead`, `ops-lead` / `Ops Lead`, `outreach-lead` / `Outreach Lead`).
*   **Permissions**:
    *   **General Local VIEW**: Can view all aspects of their own city fork.
    *   **Track-Restricted Modify**: Can modify fork components and events *only if* the target activity falls within their track (e.g., a `tech-lead` can schedule a technical event or modify a tech report for their fork, but cannot modify creative tasks).

#### 6. Fork Contributors
*   **Identification**: Holds `@Contributor` + city role + `contributor-{city}` role.
*   **Permissions**:
    *   **Local VIEW-Only**: Can view all elements of their own city fork.
    *   **No Modify Privileges**: Cannot execute administrative/update commands.

#### 7. Fork Community Members
*   **Identification**: Holds the city role (e.g., `delhi`) but **does not** hold the `@Contributor` role.
*   **Permissions**:
    *   **Public Local VIEW**: Can view public channels and resources of their city fork.
    *   **No Private Access**: Cannot view restricted contributor channels or execute bot commands.

### Dynamic Meeting Scopes

Meeting recording voice channels use role-scoping variables to dynamically establish permissions:

*   `invite`: Only explicit meeting attendees are granted join permissions.
*   `open`: Any user holding the `@Contributor` or `hq` role can join.
*   `hq`: Restricted solely to members holding the `hq` role.
*   `fork:{city}`: Restricted to members holding the `contributor-{city}` role.
*   `network:{track}`: Restricted to members holding the global track role (e.g., `tech`).
*   `fork:{city}:{track}`: Restricts access to members who hold **both** the city contributor role and the track role.

***

## Phase 0 — Repository Scaffolding

### 0.1 Initialize the Workspace

```bash
# From an empty directory named bnb-motherboard
bun init -y
```

Edit `package.json` to set up Bun workspaces:

```json
{
  "name": "bnb-motherboard",
  "private": true,
  "workspaces": [
    "apps/*",
    "packages/*",
    "plugins/*"
  ],
  "scripts": {
    "dev": "turbo run dev",
    "build": "turbo run build",
    "db:generate": "turbo run db:generate --filter=@bnb/db",
    "db:migrate": "turbo run db:migrate --filter=@bnb/db",
    "typecheck": "turbo run typecheck",
    "lint": "turbo run lint"
  }
}
```

Install Turborepo:

```bash
bun add -D turbo
```

Create `turbo.json`:

```json
{
  "$schema": "https://turbo.build/schema.json",
  "tasks": {
    "build": {
      "dependsOn": ["^build"],
      "outputs": [".next/**", "dist/**"]
    },
    "dev": {
      "cache": false,
      "persistent": true
    },
    "typecheck": {
      "dependsOn": ["^build"]
    },
    "lint": {},
    "db:generate": { "cache": false },
    "db:migrate": { "cache": false }
  }
}
```

### 0.2 Create the Root `.env.example`

Copy the secrets table from the "Required Secrets" section above into `.env.example` with placeholder values. Add `.env` to `.gitignore`.

### 0.3 Create Shared TypeScript Config

Create `tsconfig.base.json` at the root:

```json
{
  "compilerOptions": {
    "strict": true,
    "exactOptionalPropertyTypes": true,
    "noUncheckedIndexedAccess": true,
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "esModuleInterop": true,
    "skipLibCheck": true,
    "resolveJsonModule": true
  }
}
```

Every `apps/` and `packages/` directory extends this base.

### 0.4 Create All Package Directories

```bash
mkdir -p apps/web apps/api
mkdir -p packages/db packages/iam packages/provisioning packages/events packages/plugin-sdk packages/ui
mkdir -p plugins
mkdir -p docker
```

Each package needs a minimal `package.json` with the `@bnb/` scope and a `tsconfig.json` that extends `../../tsconfig.base.json`.

### 0.5 Docker Compose (Base)

Create `docker-compose.yml`:

```yaml
version: "3.9"
services:
  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: bnb
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-changeme}
      POSTGRES_DB: motherboard
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    ports:
      - "6379:6379"

  api:
    build:
      context: .
      dockerfile: docker/api.Dockerfile
    restart: unless-stopped
    env_file: .env
    environment:
      DATABASE_URL: postgres://bnb:${POSTGRES_PASSWORD:-changeme}@postgres:5432/motherboard
    ports:
      - "4000:4000"
    depends_on:
      - postgres
      - redis

  web:
    build:
      context: .
      dockerfile: docker/web.Dockerfile
    restart: unless-stopped
    env_file: .env
    environment:
      API_URL: http://api:4000
    ports:
      - "3000:3000"
    depends_on:
      - api

volumes:
  postgres_data:
```

Create placeholder Dockerfiles in `docker/`. Full content is written in Phase 5.

***

## Phase 1 — Database Schema (`@bnb/db`)

> **Search context 7** before writing schema. Verify Drizzle ORM's current API for PostgreSQL — particularly `pgTable`, relation helpers, and `drizzle-kit` config format.

### 1.1 Install Dependencies

```bash
cd packages/db
bun add drizzle-orm postgres
bun add -D drizzle-kit
```

### 1.2 Package Structure

```
packages/db/
├── src/
│   ├── schema/
│   │   ├── users.ts
│   │   ├── discord-accounts.ts
│   │   ├── groups.ts
│   │   ├── memberships.ts
│   │   ├── discord-role-mappings.ts
│   │   ├── permissions.ts
│   │   ├── grants.ts
│   │   ├── delegations.ts
│   │   ├── audit-log.ts
│   │   ├── plugin-registry.ts
│   │   └── index.ts          # re-exports all tables
│   ├── client.ts             # Drizzle client singleton
│   ├── migrate.ts            # migration runner script
│   └── index.ts
├── drizzle.config.ts
└── package.json
```

### 1.3 Schema Definitions

**`src/schema/users.ts`**
```typescript
import { pgTable, uuid, text, timestamp, boolean } from 'drizzle-orm/pg-core';

export const users = pgTable('users', {
  id: uuid('id').primaryKey().defaultRandom(),
  displayName: text('display_name').notNull(),
  email: text('email'),
  avatarUrl: text('avatar_url'),
  isActive: boolean('is_active').notNull().default(true),
  isSuperAdmin: boolean('is_super_admin').notNull().default(false),
  createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow(),
});

export type User = typeof users.$inferSelect;
export type NewUser = typeof users.$inferInsert;
```

**`src/schema/discord-accounts.ts`**
```typescript
import { pgTable, uuid, text, timestamp } from 'drizzle-orm/pg-core';
import { users } from './users';

export const discordAccounts = pgTable('discord_accounts', {
  id: uuid('id').primaryKey().defaultRandom(),
  userId: uuid('user_id').notNull().references(() => users.id, { onDelete: 'cascade' }),
  discordId: text('discord_id').notNull().unique(),
  username: text('username').notNull(),
  discriminator: text('discriminator'),
  avatarHash: text('avatar_hash'),
  accessToken: text('access_token'),
  refreshToken: text('refresh_token'),
  tokenExpiresAt: timestamp('token_expires_at', { withTimezone: true }),
  lastSyncedAt: timestamp('last_synced_at', { withTimezone: true }),
  createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow(),
});

export type DiscordAccount = typeof discordAccounts.$inferSelect;
```

**`src/schema/groups.ts`**
```typescript
import { pgTable, uuid, text, timestamp, boolean } from 'drizzle-orm/pg-core';

export const groups = pgTable('groups', {
  id: uuid('id').primaryKey().defaultRandom(),
  name: text('name').notNull().unique(),
  description: text('description'),
  isSystem: boolean('is_system').notNull().default(false), // system groups cannot be deleted
  createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow(),
});

export type Group = typeof groups.$inferSelect;
```

**`src/schema/memberships.ts`**
- Join table: `user_id` → `group_id`, with `grantedBy` (user_id nullable), `grantedAt`, `expiresAt` (nullable), `source` enum `('discord_sync' | 'manual' | 'provisioning')`.

**`src/schema/discord-role-mappings.ts`**
- Columns: `id`, `discordRoleId` (text, unique), `discordRoleName` (text), `groupId` (uuid → groups), `syncEnabled` (boolean), `createdAt`, `updatedAt`.
- This is the table the admin UI writes to when mapping Discord roles to internal groups.

**`src/schema/permissions.ts`**
- Columns: `id`, `key` (text, unique — e.g. `"iam.users.write"`), `description`, `pluginId` (nullable text — null means core), `createdAt`.

**`src/schema/grants.ts`**
- Maps a principal (user or group) to a permission key, with a resource scope (nullable), granted by whom, and when it expires.
- Columns: `id`, `principalType` (`'user' | 'group'`), `principalId` (uuid), `permissionKey` (text → permissions.key), `resourceScope` (text nullable), `grantedBy` (uuid → users), `expiresAt` (timestamp nullable), `createdAt`.

**`src/schema/delegations.ts`**
- Delegation records allowing one principal to delegate a subset of their permissions to another principal, with a written delegation reference.
- Columns: `id`, `delegatorId`, `delegateeId`, `permissionKey`, `delegationRef` (text — written authority reference), `expiresAt`, `createdAt`.

**`src/schema/audit-log.ts`**
- Append-only. Never updated or deleted.
- Columns: `id` (uuid), `actorId` (uuid nullable — null for system events), `action` (text — e.g. `"user.created"`, `"group.member.added"`), `targetType` (text), `targetId` (text), `metadata` (jsonb), `createdAt`.

**`src/schema/plugin-registry.ts`**
- Columns: `id` (text — plugin's declared ID, unique), `name`, `version`, `description`, `isEnabled` (boolean), `installedAt`, `config` (jsonb).

### 1.4 Drizzle Config

**`drizzle.config.ts`**:
```typescript
import { defineConfig } from 'drizzle-kit';

export default defineConfig({
  schema: './src/schema/index.ts',
  out: './migrations',
  dialect: 'postgresql',
  dbCredentials: {
    url: process.env.DATABASE_URL!,
  },
});
```

### 1.5 Client Singleton

**`src/client.ts`**:
```typescript
import { drizzle } from 'drizzle-orm/postgres-js';
import postgres from 'postgres';
import * as schema from './schema';

const connectionString = process.env.DATABASE_URL;
if (!connectionString) throw new Error('DATABASE_URL is required');

const sql = postgres(connectionString);
export const db = drizzle(sql, { schema });
export type Db = typeof db;
```

### 1.6 Generate and Run Initial Migration

```bash
cd packages/db
bunx drizzle-kit generate
bunx drizzle-kit migrate
```

Commit the generated migration files.

***

## Phase 2 — IAM Package (`@bnb/iam`)

> **Search context 7** to verify your schema types from Phase 1 are accurately reflected here before writing policy logic.

The IAM package is the single source of truth for "can this principal do this action on this resource?" It has no HTTP layer — it is imported by the API and evaluated per-request.

### 2.1 Package Structure

```
packages/iam/
├── src/
│   ├── principal.ts        # Resolve a user's effective groups and permissions
│   ├── policy.ts           # can(principal, permissionKey, resourceScope?) → boolean
│   ├── audit.ts            # writeAuditEntry(...)
│   ├── system-groups.ts    # Seed constants for built-in groups
│   └── index.ts
└── package.json
```

### 2.2 Principal Resolution

**`src/principal.ts`**

```typescript
import { db } from '@bnb/db';
import { memberships, grants, users } from '@bnb/db/schema';
import { eq } from 'drizzle-orm';

export type ResolvedPrincipal = {
  userId: string;
  groupIds: string[];
  isSuperAdmin: boolean;
};

/**
 * Resolves all groups a user belongs to.
 * Call this once per request and cache the result in the request context.
 */
export async function resolvePrincipal(userId: string): Promise<ResolvedPrincipal> {
  const user = await db.query.users.findFirst({ where: eq(users.id, userId) });
  if (!user || !user.isActive) throw new Error('User not found or inactive');

  const userMemberships = await db.query.memberships.findMany({
    where: eq(memberships.userId, userId),
  });

  return {
    userId,
    groupIds: userMemberships.map((m) => m.groupId),
    isSuperAdmin: user.isSuperAdmin,
  };
}
```

### 2.3 Policy Evaluator

**`src/policy.ts`**

```typescript
import { db } from '@bnb/db';
import { grants } from '@bnb/db/schema';
import { and, eq, inArray, or, isNull, gt } from 'drizzle-orm';
import type { ResolvedPrincipal } from './principal';

/**
 * Evaluates whether the resolved principal holds the given permission,
 * optionally scoped to a specific resource.
 *
 * Super admins bypass all permission checks.
 */
export async function can(
  principal: ResolvedPrincipal,
  permissionKey: string,
  resourceScope?: string,
): Promise<boolean> {
  if (principal.isSuperAdmin) return true;

  const now = new Date();

  // Build principal conditions: user direct grants OR any of their group grants
  const principalConditions = or(
    and(eq(grants.principalType, 'user'), eq(grants.principalId, principal.userId)),
    ...(principal.groupIds.length > 0
      ? [and(eq(grants.principalType, 'group'), inArray(grants.principalId, principal.groupIds))]
      : []),
  );

  const matchingGrants = await db.query.grants.findMany({
    where: and(
      principalConditions,
      eq(grants.permissionKey, permissionKey),
      or(isNull(grants.expiresAt), gt(grants.expiresAt, now)),
    ),
  });

  if (matchingGrants.length === 0) return false;

  // If no resourceScope required, any grant suffices
  if (!resourceScope) return true;

  // Otherwise, at least one grant must have null scope (wildcard) or match exactly
  return matchingGrants.some(
    (g) => g.resourceScope === null || g.resourceScope === resourceScope,
  );
}
```

### 2.4 Audit Writer

**`src/audit.ts`**

```typescript
import { db } from '@bnb/db';
import { auditLog } from '@bnb/db/schema';

export async function writeAuditEntry(entry: {
  actorId?: string;
  action: string;
  targetType: string;
  targetId: string;
  metadata?: Record<string, unknown>;
}): Promise<void> {
  await db.insert(auditLog).values({
    actorId: entry.actorId ?? null,
    action: entry.action,
    targetType: entry.targetType,
    targetId: entry.targetId,
    metadata: entry.metadata ?? {},
  });
}
```

### 2.5 System Groups Seed

**`src/system-groups.ts`**

Define constant IDs for system groups that are created on first boot:

```typescript
export const SYSTEM_GROUPS = {
  SUPER_ADMIN: 'sg_super_admin',
  STAFF: 'sg_staff',
  FORK_LEAD: 'sg_fork_lead',
  CONTRIBUTOR: 'sg_contributor',
  MEMBER: 'sg_member',
} as const;
```

The API server seeds these groups on startup if they do not exist.

***

## Phase 3 — Event Bus (`@bnb/events`)

### 3.1 Typed Event Definitions

```
packages/events/
├── src/
│   ├── event-types.ts      # All event type definitions
│   ├── bus.ts              # EventEmitter-based bus
│   └── index.ts
└── package.json
```

**`src/event-types.ts`** — define a discriminated union:

```typescript
export type MothboardEvent =
  | { type: 'user.created'; payload: { userId: string } }
  | { type: 'user.deactivated'; payload: { userId: string } }
  | { type: 'group.member.added'; payload: { userId: string; groupId: string; source: string } }
  | { type: 'group.member.removed'; payload: { userId: string; groupId: string } }
  | { type: 'discord.sync.completed'; payload: { syncedCount: number; errors: string[] } }
  | { type: 'discord.role.mapped'; payload: { discordRoleId: string; groupId: string } }
  | { type: 'plugin.registered'; payload: { pluginId: string } }
  | { type: 'plugin.unregistered'; payload: { pluginId: string } };
```

**`src/bus.ts`** — Typed EventEmitter wrapper:

```typescript
import { EventEmitter } from 'node:events';
import type { MothboardEvent } from './event-types';

class MotherboardEventBus extends EventEmitter {
  emit<E extends MothboardEvent>(event: E): boolean {
    return super.emit(event.type, event.payload);
  }

  on<T extends MothboardEvent['type']>(
    event: T,
    listener: (payload: Extract<MothboardEvent, { type: T }>['payload']) => void,
  ): this {
    return super.on(event, listener);
  }
}

export const bus = new MotherboardEventBus();
```

***

## Phase 4 — Plugin SDK (`@bnb/plugin-sdk`)

This is the most important package in the system. It is the contract between the core and every plugin — first-party or third-party. Document it fully in a `README.md` inside the package.

> **Search context 7** before writing plugin loading logic in the API to confirm Fastify 5's plugin system (`fastify-plugin`, `register`) works as described here.

### 4.1 Package Structure

```
packages/plugin-sdk/
├── src/
│   ├── types.ts             # All public types a plugin author uses
│   ├── define-plugin.ts     # definePlugin() factory
│   ├── plugin-context.ts    # Context object passed to plugin lifecycle hooks
│   ├── ui-manifest.ts       # UI registration contract
│   ├── event-contract.ts    # Event bus subscription helpers
│   ├── permission-contract.ts # Permission declaration helpers
│   └── index.ts
├── README.md
└── package.json
```

### 4.2 Plugin Manifest Type

**`src/types.ts`**

```typescript
import type { FastifyInstance } from 'fastify';
import type { Db } from '@bnb/db';
import type { MothboardEvent } from '@bnb/events';

/**
 * The context object passed to every plugin lifecycle hook.
 * Provides safe, scoped access to core infrastructure.
 */
export type PluginContext = {
  /** Drizzle database client. Plugin may run its own migrations here. */
  db: Db;
  /** Plugin's declared ID. Used for namespacing routes and tables. */
  pluginId: string;
  /** Evaluates a permission for a given user. Core delegates to @bnb/iam. */
  can: (userId: string, permissionKey: string, resourceScope?: string) => Promise<boolean>;
  /** Write a structured audit log entry. */
  audit: (entry: {
    actorId?: string;
    action: string;
    targetType: string;
    targetId: string;
    metadata?: Record<string, unknown>;
  }) => Promise<void>;
  /** Emit a typed event to the event bus. */
  emit: <E extends MothboardEvent>(event: E) => void;
  /** Subscribe to a typed event from the event bus. */
  on: <T extends MothboardEvent['type']>(
    event: T,
    listener: (payload: Extract<MothboardEvent, { type: T }>['payload']) => void,
  ) => void;
};

/**
 * A declared permission that the plugin owns.
 * Permissions are keyed as `<pluginId>.<resource>.<action>`.
 */
export type PermissionDeclaration = {
  key: string;
  description: string;
};

/**
 * A UI panel registration.
 * The plugin declares panel metadata; the Next.js shell lazy-loads
 * the panel's React component from the plugin's published package.
 */
export type UiPanelDeclaration = {
  /** Unique panel ID within this plugin. */
  id: string;
  /** Human-readable panel title shown in navigation. */
  title: string;
  /**
   * The route path segment this panel mounts at.
   * E.g. "tasks" → renders at /plugins/tasks
   */
  routeSegment: string;
  /**
   * Navigation placement: 'sidebar' shows a persistent link.
   * 'modal' means the panel is opened programmatically.
   * 'embedded' means it is injected into a core page slot.
   */
  placement: 'sidebar' | 'modal' | 'embedded';
  /**
   * The permission key required to see this panel.
   * If null, any authenticated user can see it.
   */
  requiredPermission: string | null;
  /**
   * Icon identifier from the shared icon set (Lucide icon name).
   */
  icon: string;
};

/**
 * A plugin migration function.
 * Receives the raw Drizzle db instance.
 * Must be idempotent (safe to run multiple times).
 */
export type MigrationFn = (db: Db) => Promise<void>;

/**
 * The full plugin manifest.
 * Returned by definePlugin().
 */
export type PluginManifest = {
  /** Globally unique. Use reverse-domain style: "org.bnb.tasks" */
  id: string;
  name: string;
  version: string;
  description: string;
  /**
   * Called once when the plugin is loaded.
   * Register Fastify routes, listeners, etc. here.
   * Routes are automatically prefixed with /api/plugins/<pluginId>.
   */
  onLoad: (fastify: FastifyInstance, ctx: PluginContext) => Promise<void>;
  /**
   * Called once when the plugin is unloaded (server shutdown or admin disable).
   */
  onUnload?: (ctx: PluginContext) => Promise<void>;
  /**
   * Database migration functions run before onLoad.
   * Must be idempotent.
   */
  migrations?: MigrationFn[];
  /**
   * Permissions this plugin declares.
   * Core will create these in the permissions table on load if missing.
   */
  permissions?: PermissionDeclaration[];
  /**
   * UI panels this plugin contributes to the web dashboard.
   */
  uiPanels?: UiPanelDeclaration[];
  /**
   * Event types this plugin emits (documentation only — for tooling/introspection).
   */
  emits?: MothboardEvent['type'][];
  /**
   * Event types this plugin subscribes to.
   * Subscriptions are registered automatically during onLoad.
   */
  subscribes?: MothboardEvent['type'][];
};
```

### 4.3 `definePlugin` Factory

**`src/define-plugin.ts`**

```typescript
import type { PluginManifest } from './types';

/**
 * Type-safe factory for declaring a plugin.
 * Provides autocomplete and compile-time validation of the manifest.
 *
 * @example
 * export default definePlugin({
 *   id: 'org.bnb.tasks',
 *   name: 'Tasks',
 *   version: '1.0.0',
 *   description: 'Task management for the bnb network',
 *   async onLoad(fastify, ctx) {
 *     fastify.get('/list', async (req, reply) => { ... });
 *   },
 *   permissions: [
 *     { key: 'org.bnb.tasks.task.read', description: 'View tasks' },
 *     { key: 'org.bnb.tasks.task.write', description: 'Create and update tasks' },
 *   ],
 *   uiPanels: [
 *     {
 *       id: 'main',
 *       title: 'Tasks',
 *       routeSegment: 'tasks',
 *       placement: 'sidebar',
 *       requiredPermission: 'org.bnb.tasks.task.read',
 *       icon: 'CheckSquare',
 *     },
 *   ],
 * });
 */
export function definePlugin(manifest: PluginManifest): PluginManifest {
  return manifest;
}
```

### 4.4 UI Component Contract

Plugins that provide UI panels must:

1. Export a default React component from their package's `ui` entry point (declared in their `package.json` `exports` map as `"./ui"`).
2. The component receives a `PluginPanelProps` object:

```typescript
// In @bnb/plugin-sdk
export type PluginPanelProps = {
  /** The current authenticated user's ID */
  userId: string;
  /** A pre-authenticated fetch function scoped to this plugin's API routes */
  apiFetch: (path: string, init?: RequestInit) => Promise<Response>;
};
```

3. The component **must use components from `@bnb/ui`** for all UI — it must not ship its own design system. Buttons, inputs, tables, dialogs — all from `@bnb/ui`.
4. The Next.js shell dynamically imports the plugin's UI component using `next/dynamic` and wraps it in a `<Suspense>` boundary with a skeleton loader from `@bnb/ui`.

### 4.5 Plugin Loader (used by API)

Implement `packages/plugin-sdk/src/loader.ts`:

```typescript
/**
 * PluginLoader manages the lifecycle of all registered plugins.
 * It is instantiated once in the Fastify server and holds references
 * to all loaded plugin manifests and their contexts.
 */
export class PluginLoader {
  private loaded: Map<string, PluginManifest> = new Map();

  async load(manifest: PluginManifest, fastify: FastifyInstance, ctx: PluginContext): Promise<void>;
  async unload(pluginId: string, ctx: PluginContext): Promise<void>;
  getLoaded(): PluginManifest[];
  getUiPanels(): UiPanelDeclaration[];  // Used by the web API endpoint for nav
}
```

***

## Phase 5 — Provisioning Worker (`@bnb/provisioning`)

> **Search context 7** before implementing the Discord API calls. Verify the `discord.js` REST client or `undici` usage for guild member fetching with the `guilds.members.read` scope. Do not guess at rate limit behavior.

### 5.1 What the Worker Does

1. Fetches all members of the configured Discord guild using the bot token.
2. For each member, looks up their `discordId` in `discord_accounts`.
3. For each Discord role on the member, looks up the `discord_role_mappings` table.
4. If a mapping exists and `syncEnabled = true`, ensures the user is in the mapped internal group.
5. Removes a user from a group if they no longer have the mapped Discord role.
6. Emits `discord.sync.completed` after each run.
7. Writes audit entries for every group membership change.

### 5.2 Package Structure

```
packages/provisioning/
├── src/
│   ├── discord-client.ts   # Thin wrapper around Discord REST API
│   ├── sync-worker.ts      # Main sync logic
│   ├── scheduler.ts        # Setinterval-based scheduler (or node-cron)
│   └── index.ts
└── package.json
```

### 5.3 Discord Client

**`src/discord-client.ts`** — use `undici` (Bun-native) or the `@discordjs/rest` package. Do NOT use `node-fetch`. Implement:

- `getGuildMembers(guildId: string): Promise<GuildMember[]>` — paginates through all guild members using the `after` query parameter. Each page is 1000 members.
- `getRoles(guildId: string): Promise<Role[]>` — fetches current role list for display name sync.

`GuildMember` type:
```typescript
type GuildMember = {
  user: { id: string; username: string; avatar: string | null };
  roles: string[]; // array of role IDs
  nick: string | null;
};
```

### 5.4 Sync Logic

**`src/sync-worker.ts`**

```typescript
export async function runSync(): Promise<{ syncedCount: number; errors: string[] }> {
  // 1. Fetch all guild members from Discord
  // 2. Fetch all role mappings from db where syncEnabled = true
  // 3. For each guild member:
  //    a. Find matching internal user by discordId
  //    b. If no match, skip (user has not logged in yet)
  //    c. For each of the user's Discord roles:
  //       - If role has a mapping, ensure user is in that group
  //    d. For each group the user is in with source='discord_sync':
  //       - If the mapped Discord role is no longer present, remove them
  // 4. Update lastSyncedAt on discord_accounts
  // 5. Emit discord.sync.completed
}
```

All membership changes must:
- Write an audit entry via `@bnb/iam`'s `writeAuditEntry`.
- Emit `group.member.added` or `group.member.removed` on the event bus.

### 5.5 Scheduler

Run the sync on a schedule using `node-cron` or a simple `setInterval`. The interval is configurable via `SYNC_INTERVAL_MINUTES` env variable (default: 15). The scheduler is started inside the API server's `onReady` hook, not as a separate process, to keep the Docker service count minimal.

***

## Phase 6 — Fastify API (`apps/api`)

> **Search context 7** before implementing Fastify plugins, decorators, and route schemas. Verify Fastify 5 breaking changes from Fastify 4 — particularly typed request/reply generics.

### 6.1 Install Dependencies

```bash
cd apps/api
bun add fastify @fastify/cookie @fastify/session @fastify/cors fastify-plugin
bun add @bnb/db @bnb/iam @bnb/events @bnb/provisioning @bnb/plugin-sdk
bun add -D @types/node
```

### 6.2 Directory Structure

```
apps/api/
├── src/
│   ├── server.ts               # Fastify instance creation + plugin registration
│   ├── index.ts                # Entry point: start server
│   ├── plugins/
│   │   ├── auth.ts             # Session + JWT verification decorator
│   │   ├── iam.ts              # Attaches resolvePrincipal and can to request
│   │   └── plugin-loader.ts    # Loads and mounts plugin manifests
│   ├── routes/
│   │   ├── auth/
│   │   │   ├── discord-oauth.ts   # OAuth callback handler
│   │   │   └── session.ts         # GET /auth/me, POST /auth/logout
│   │   ├── iam/
│   │   │   ├── users.ts           # CRUD for users
│   │   │   ├── groups.ts          # CRUD for groups
│   │   │   ├── grants.ts          # Grant/revoke permissions
│   │   │   └── discord-mappings.ts # UI-driven role mapping
│   │   ├── provisioning/
│   │   │   └── sync.ts            # POST /provisioning/sync (trigger manual sync)
│   │   ├── plugins/
│   │   │   └── manifest.ts        # GET /plugins/manifest (returns loaded plugins + UI panels)
│   │   ├── audit/
│   │   │   └── log.ts             # GET /audit (paginated)
│   │   └── bot/
│   │       └── webhook.ts         # POST /bot/webhook (signed with API_INTERNAL_SECRET)
│   └── middleware/
│       ├── require-auth.ts        # Prehandler: rejects unauthenticated requests
│       └── require-permission.ts  # Prehandler factory: requires a permission key
├── tsconfig.json
└── package.json
```

### 6.3 Auth Flow

**Discord OAuth is handled entirely in Next.js via NextAuth.js.** After NextAuth completes the Discord OAuth flow:

1. NextAuth stores the Discord access token and user info in its session.
2. The Next.js app makes API calls to Fastify with a session cookie or a JWT issued by NextAuth.
3. The Fastify `auth` plugin verifies the NextAuth JWT (using the shared `NEXTAUTH_SECRET`) on every request.
4. On first login, the API creates a `users` record and a `discord_accounts` record.

**Do not implement a separate OAuth flow in Fastify.** NextAuth owns the browser-facing OAuth dance.

### 6.4 Bot Webhook

The existing Discord bot calls `POST /bot/webhook` to:
- Report events (role changes, member joins/leaves).
- Trigger sync for a specific user.

This endpoint verifies the `X-Internal-Secret` header against `API_INTERNAL_SECRET`. On a role change event, it calls `runSync()` for the affected user only (a targeted sync, not a full guild sync).

Request body schema:
```typescript
type BotWebhookPayload =
  | { event: 'member.role_update'; discordId: string }
  | { event: 'member.join'; discordId: string; username: string }
  | { event: 'member.leave'; discordId: string };
```

### 6.5 Plugin Route Mounting

The `plugin-loader.ts` Fastify plugin:
1. Iterates over all manifests in `PluginLoader.getLoaded()`.
2. For each plugin, calls `fastify.register(async (pluginScope) => { await manifest.onLoad(pluginScope, ctx) }, { prefix: /api/plugins/${manifest.id} })`.
3. This gives each plugin its own Fastify scope for error handling and hooks.

### 6.6 Startup Sequence

In `server.ts`, the startup sequence is:

1. Register Fastify plugins (cookie, session, cors, iam, auth).
2. Register all core routes.
3. Seed system groups (idempotent).
4. Seed core permissions (idempotent).
5. Load plugin manifests (run migrations, register routes, register event subscriptions).
6. Start provisioning scheduler.
7. Listen on port 4000.

***

## Phase 7 — Next.js Web App (`apps/web`)

> **Search context 7** before implementing Next.js App Router patterns, particularly `layout.tsx` structure, `use client` / `use server` boundary conventions, and NextAuth v5 session access.

### 7.1 Install Dependencies

```bash
cd apps/web
bun add next react react-dom next-auth
bun add @bnb/ui
bun add -D @types/react @types/node typescript
```

### 7.2 Directory Structure

```
apps/web/
├── app/
│   ├── layout.tsx                  # Root layout (providers, fonts, nav shell)
│   ├── page.tsx                    # Redirect to /dashboard or /login
│   ├── (auth)/
│   │   └── login/page.tsx          # Login page with Discord OAuth button
│   ├── (dashboard)/
│   │   ├── layout.tsx              # Authenticated layout with sidebar
│   │   ├── dashboard/page.tsx      # Home dashboard
│   │   ├── users/page.tsx          # IAM: user list
│   │   ├── users/[id]/page.tsx     # IAM: user detail + group memberships
│   │   ├── groups/page.tsx         # IAM: group list
│   │   ├── groups/[id]/page.tsx    # IAM: group detail + member list
│   │   ├── discord-mappings/page.tsx  # Admin: map Discord roles to groups
│   │   ├── grants/page.tsx         # IAM: grant/revoke permissions
│   │   ├── audit/page.tsx          # Audit log viewer
│   │   └── plugins/
│   │       └── [pluginId]/
│   │           └── [[...slug]]/page.tsx  # Dynamic plugin UI mount point
│   └── api/
│       └── auth/[...nextauth]/route.ts   # NextAuth handler
├── components/                     # App-level components (imports from @bnb/ui)
├── lib/
│   ├── api-client.ts               # Typed fetch wrapper for Fastify API
│   └── auth.ts                     # NextAuth config (Discord provider)
├── next.config.ts
└── tsconfig.json
```

### 7.3 NextAuth Configuration

**`lib/auth.ts`**:
```typescript
import NextAuth from 'next-auth';
import Discord from 'next-auth/providers/discord';

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    Discord({
      clientId: process.env.DISCORD_CLIENT_ID!,
      clientSecret: process.env.DISCORD_CLIENT_SECRET!,
      authorization: {
        params: {
          // Request guild member read scope to fetch roles
          scope: 'identify email guilds.members.read',
        },
      },
    }),
  ],
  secret: process.env.NEXTAUTH_SECRET,
  callbacks: {
    async jwt({ token, account, profile }) {
      if (account) {
        token.discordId = profile?.id;
        token.accessToken = account.access_token;
      }
      return token;
    },
    async session({ session, token }) {
      session.user.discordId = token.discordId as string;
      return session;
    },
    async signIn({ account, profile }) {
      // On sign-in, call the Fastify API to upsert the user
      // This ensures a user record exists before any further requests
      await fetch(`${process.env.API_URL}/auth/upsert`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Internal-Secret': process.env.API_INTERNAL_SECRET!,
        },
        body: JSON.stringify({
          discordId: profile?.id,
          username: profile?.username,
          email: profile?.email,
          avatarHash: profile?.avatar,
          accessToken: account?.access_token,
          refreshToken: account?.refresh_token,
          tokenExpiresAt: account?.expires_at ? new Date(account.expires_at * 1000) : null,
        }),
      });
      return true;
    },
  },
});
```

### 7.4 Plugin UI Mount Point

**`app/(dashboard)/plugins/[pluginId]/[[...slug]]/page.tsx`**:

```typescript
import dynamic from 'next/dynamic';
import { Skeleton } from '@bnb/ui';

// Load the plugin's UI component dynamically.
// Plugin packages must be installed in apps/web for this to work.
// The plugin registry API provides the list of installed plugins and their panel metadata.
export default async function PluginPage({ params }: { params: { pluginId: string } }) {
  const PluginPanel = dynamic(
    () => import(`@bnb-plugins/${params.pluginId}/ui`).catch(() => () => <div>Plugin not found</div>),
    { loading: () => <Skeleton className="h-96 w-full" />, ssr: false },
  );

  return <PluginPanel />;
}
```

**Note:** Third-party plugin packages must follow the naming convention `@bnb-plugins/<pluginId>` and be installed in `apps/web/package.json` before the web app is rebuilt.

### 7.5 Sidebar Navigation

The sidebar is built server-side. It fetches `/api/plugins/manifest` from the Fastify API (using the internal `API_URL`) to get the list of active plugin UI panels with `placement: 'sidebar'` and renders them as navigation links. The sidebar also includes hardcoded core links (Dashboard, Users, Groups, Discord Mappings, Grants, Audit Log).

***

## Phase 8 — Shared UI Package (`@bnb/ui`)

### 8.1 Setup

```bash
cd packages/ui
bun add react radix-ui tailwindcss
bun add -D @types/react
```

The package exports primitive, accessible components. All components accept standard HTML props via `ComponentPropsWithoutRef`. Every component must have a `displayName`.

### 8.2 Required Base Components

These components must exist at minimum before any plugin can be developed:

- `Button` (variants: primary, secondary, destructive, ghost; sizes: sm, md, lg)
- `Input` (with label and error state)
- `Select` (Radix-based)
- `Dialog` / `DialogTrigger` / `DialogContent` (Radix-based)
- `Table` / `TableHead` / `TableRow` / `TableCell`
- `Badge` (variants: default, success, warning, error)
- `Skeleton` (loading placeholder)
- `Spinner`
- `Avatar` (with fallback initials)
- `Card` / `CardHeader` / `CardContent`
- `Alert` (info, warning, error)
- `Pagination`
- `DropdownMenu` (Radix-based)

All components use Tailwind CSS. The package ships a `tailwind.config.ts` that consuming apps extend.

***

## Phase 9 — Discord Role Mapping UI

This is the key admin screen. It lives at `/discord-mappings` in the web app.

### 9.1 What It Does

1. Fetches the current list of Discord roles from `GET /api/iam/discord-roles` (the Fastify API fetches this from Discord using the bot token).
2. Fetches the current list of internal groups from `GET /api/iam/groups`.
3. Fetches current mappings from `GET /api/iam/discord-mappings`.
4. Renders a table: one row per Discord role. Each row has:
   - Role name and color swatch.
   - A `<Select>` to choose which internal group it maps to (or "No mapping").
   - A toggle for `syncEnabled`.
5. Saves changes via `PUT /api/iam/discord-mappings` (upsert — only changed rows).

### 9.2 No Optimistic Updates

This screen is not optimistic. On save, show a spinner, wait for the API response, then refresh. Mapping changes are consequential — do not show false success states.

***

## Phase 10 — Dockerfiles and Production Compose

### 10.1 API Dockerfile (`docker/api.Dockerfile`)

```dockerfile
FROM oven/bun:1-alpine AS base
WORKDIR /app

FROM base AS deps
COPY package.json bun.lockb turbo.json ./
COPY packages/db/package.json ./packages/db/
COPY packages/iam/package.json ./packages/iam/
COPY packages/events/package.json ./packages/events/
COPY packages/provisioning/package.json ./packages/provisioning/
COPY packages/plugin-sdk/package.json ./packages/plugin-sdk/
COPY apps/api/package.json ./apps/api/
RUN bun install --frozen-lockfile

FROM base AS builder
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN bun run build --filter=apps/api...

FROM base AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/apps/api/dist ./dist
COPY --from=builder /app/packages ./packages
COPY --from=builder /app/node_modules ./node_modules
CMD ["bun", "run", "dist/index.js"]
```

**Note:** Run `bunx drizzle-kit migrate` as an init container or pre-start step. Add a `migrate` service to `docker-compose.prod.yml` that runs migrations and exits before the API starts.

### 10.2 Web Dockerfile (`docker/web.Dockerfile`)

```dockerfile
FROM oven/bun:1-alpine AS base
WORKDIR /app

FROM base AS deps
COPY package.json bun.lockb turbo.json ./
COPY packages/ui/package.json ./packages/ui/
COPY apps/web/package.json ./apps/web/
RUN bun install --frozen-lockfile

FROM base AS builder
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN bun run build --filter=apps/web

FROM base AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/apps/web/.next ./.next
COPY --from=builder /app/apps/web/public ./public
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/apps/web/package.json ./package.json
CMD ["bun", "run", "start"]
```

### 10.3 Production Docker Compose (`docker-compose.prod.yml`)

Override the base compose for production:

```yaml
version: "3.9"
services:
  migrate:
    build:
      context: .
      dockerfile: docker/api.Dockerfile
    command: ["bun", "run", "packages/db/src/migrate.ts"]
    env_file: .env
    depends_on:
      - postgres
    restart: on-failure

  api:
    depends_on:
      migrate:
        condition: service_completed_successfully

  web:
    environment:
      NODE_ENV: production
```

Run in production with:
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

***

## Coding Conventions

### Naming

- **Files:** `kebab-case.ts`
- **Classes:** `PascalCase`
- **Functions and variables:** `camelCase`
- **Constants:** `SCREAMING_SNAKE_CASE` for module-level constants, `camelCase` for local
- **Database columns:** `snake_case` (Drizzle handles the TypeScript ↔ SQL mapping)
- **TypeScript types and interfaces:** `PascalCase`, prefix `I` is forbidden
- **Zod schemas:** suffix `Schema` (e.g. `CreateUserSchema`)
- **React components:** `PascalCase`, one component per file, file name matches component name

### TypeScript

- `strict: true`, `exactOptionalPropertyTypes: true`, `noUncheckedIndexedAccess: true` — all enforced.
- Never use `as any`. Use `as unknown as T` only as an escape hatch with a comment explaining why.
- Never suppress type errors with `@ts-ignore`. Use `@ts-expect-error` with an explanation when unavoidable.
- Prefer type narrowing and discriminated unions over casting.
- All async functions that can fail must return a typed `Result<T, E>` or throw typed errors — do not return `undefined` on failure.

### API Design

- All API routes use JSON body and JSON response.
- All routes return consistent envelope: `{ data: T }` for success, `{ error: { code: string; message: string } }` for failure.
- HTTP status codes: 200 (OK), 201 (Created), 400 (Bad Request), 401 (Unauthenticated), 403 (Forbidden), 404 (Not Found), 422 (Validation Error), 500 (Internal Error).
- All input is validated with Zod schemas. Fastify's `schema` option uses JSON Schema; convert Zod schemas to JSON Schema using `zod-to-json-schema` or use `fastify-type-provider-zod`.
- All list endpoints are paginated with `limit` and `cursor` query params.

### Error Handling

- Never swallow errors silently.
- The Fastify global error handler logs the full error and returns a safe, sanitized response.
- Never expose internal error messages, stack traces, or database errors to API responses.
- Use a custom `AppError` class with a `code` string for business logic errors.

### Git & Commit Conventions

- **Always perform atomic commits:** Keep commits small, focused, and representing a single logical change. Do not group unrelated changes into a single commit.
- **Use conventional commits:** Format messages using `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`.

***

## Anti-Hallucination Checkpoints

The agent MUST perform a context 7 search at the following moments:

1. **Before writing any Drizzle schema** — verify current `drizzle-orm` PostgreSQL API.
2. **Before writing the IAM policy evaluator** — verify the Drizzle query builder conditions API (`and`, `or`, `inArray`, `isNull`, `gt`).
3. **Before writing the Fastify server** — verify Fastify 5 `register`, decorators, and type provider patterns.
4. **Before implementing NextAuth v5** — verify `next-auth` v5 callback signatures, `signIn` hook, and session shape.
5. **Before writing the Discord guild member fetch** — verify rate limits, pagination params, and required bot permissions.
6. **Before the plugin loader's `dynamic import` in Next.js** — verify `next/dynamic` usage in App Router.
7. **Before writing any Dockerfile** — verify the `oven/bun` base image tag and Bun build output paths.

If context 7 is unavailable, pause and run `bunx skills find <topic>` before proceeding.

***

## Definition of Done (Per Phase)

Each phase is complete when:

- [ ] All TypeScript compiles with `bun run typecheck` — zero errors.
- [ ] No `any` types introduced.
- [ ] All new routes have Zod-validated input.
- [ ] All new database operations have correct schema references (run `bunx drizzle-kit check` if available).
- [ ] All public functions have JSDoc comments.
- [ ] Docker Compose brings the service up with `docker compose up` — no errors in logs.
- [ ] The feature is reachable and functional end-to-end.

Do not begin the next phase until the current phase's definition of done is met.
