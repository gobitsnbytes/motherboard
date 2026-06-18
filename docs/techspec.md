# bnb-motherboard — Technical Specification (FastAPI Edition)

> **Before starting any phase:** Run `bunx skills find <topic>` to locate relevant skill documentation for the task at hand (e.g. `bunx skills find drizzle orm`, `bunx skills find nextjs app router`, `bunx skills find discord oauth`). For Python/FastAPI backend tasks, verify with `bunx skills find fastapi` and `bunx skills find fastapi-patterns`. Use the outputs to guide implementation — do not guess at APIs.
>
> **Anti-hallucination rule:** After every 3–4 files created or every major subsystem completed, stop and search your context window (context 7 or equivalent) for the latest state of relevant interfaces, schemas, and type contracts before continuing. Write code against what actually exists in the codebase, not against memory.

***

## What Is Being Built

**bnb-motherboard** is the internal operations platform for the bits&bytes network. It serves as:

- An **Identity & Access Management (IAM) core** — Discord is the upstream identity provider. Users log in via Discord OAuth. Discord guild roles are imported via the Discord API and mapped to internal groups through an admin UI.
- A **provisioning engine** — a sync worker keeps internal users, roles, and entitlements in sync with the Discord guild on a schedule and on-demand.
- A **plugin platform** — an elaborately specified SDK allows first- and third-party plugins to register routes (with the FastAPI app), UI panels (using the Next.js shell and shared component library), event bus subscriptions, database migrations, permissions, and audit entries.
- A **web dashboard** — Next.js 15 frontend decoupled from the FastAPI backend via a clean REST API boundary.
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
| `DATABASE_URL` | Postgres connection string | Self-hosted container (auto-generated in docker-compose, e.g., `postgresql+asyncpg://bnb:pwd@postgres:5432/motherboard`) |
| `SESSION_SECRET` | Long random string for cookie signing / sessions | Generate: `openssl rand -hex 64` |
| `API_INTERNAL_SECRET` | Shared secret between API and Bot | Generate: `openssl rand -hex 32` |
| `NEXTAUTH_SECRET` | NextAuth.js secret | Generate: `openssl rand -hex 32` |
| `NEXTAUTH_URL` | Public URL of the Next.js app | VPS domain or `http://localhost:3000` |
| `API_URL` | Internal URL of FastAPI API | `http://api:8000` in Docker, `http://localhost:8000` locally |

**Discord OAuth redirect URI** to register in the Developer Portal:
- `http://localhost:3000/api/auth/callback/discord` (development)
- `https://<your-domain>/api/auth/callback/discord` (production)

***

## Monorepo Structure

The project has a hybrid structure: Next.js frontend and React shared libraries use Bun workspace orchestration, while the FastAPI backend uses Python with `uv` package management.

```
bnb-motherboard/
├── apps/
│   ├── web/                    # Next.js 15 App Router (frontend)
│   └── api/                    # FastAPI (Python) backend
│       ├── app/
│       │   ├── main.py         # Application root & lifespan
│       │   ├── config.py       # Pydantic-settings config
│       │   ├── database.py     # SQLAlchemy DB connection & sessionmaker
│       │   ├── dependencies.py # FastAPI dependencies (auth, principal resolver)
│       │   ├── db/             # SQLAlchemy ORM models and seeds
│       │   ├── iam/            # IAM: Principal resolver, policy evaluation, audit
│       │   ├── provisioning/   # Discord member sync worker & scheduler
│       │   ├── events/         # Redis-backed/in-process Typed Event Bus
│       │   ├── plugin_sdk/     # Plugin SDK engine and loader
│       │   ├── routers/        # API route files
│       │   └── schemas/        # Pydantic v2 schemas (request/response validation)
│       ├── alembic/            # Database migration revisions
│       ├── alembic.ini
│       ├── pyproject.toml      # uv-managed python configuration
│       └── tests/              # pytest suite
├── packages/
│   └── ui/                     # Shared React component library (Next.js + Plugin UIs)
├── plugins/                    # First- and third-party operational plugins
│   └── <plugin_id>/
│       ├── ui/                 # React frontend entry points (rendered in web dashboard)
│       └── api/                # Python backend APIRouter entry points (mounted in FastAPI)
├── docker/
│   ├── api.Dockerfile          # Python / uv Dockerfile
│   └── web.Dockerfile          # Bun / Next.js Dockerfile
├── docker-compose.yml
├── docker-compose.prod.yml
├── .env.example
├── .env                        # gitignored
├── package.json                # Bun workspace root (contains apps/web & packages/ui)
└── AGENTS.md                   # Agent guidelines, kept updated
```

**Naming conventions:**
- TypeScript packages use `@bnb/` scope (e.g. `@bnb/ui`).
- Python code follows PEP 8 styling conventions (directories and file names: `snake_case`).
- TypeScript files: `kebab-case`.

***

## Technology Versions

| Layer | Technology |
|---|---|
| Runtime (Frontend) | Bun (latest stable) |
| Runtime (Backend) | Python 3.11 / 3.12 |
| Package Manager (FE) | Bun workspaces |
| Package Manager (BE) | uv (Astral) |
| Frontend | Next.js 15 App Router, React 19, TypeScript |
| Backend | FastAPI 0.111+, Pydantic v2, Python |
| Database | PostgreSQL 16 (Docker container) |
| ORM (Backend) | SQLAlchemy 2.0 (asyncpg) + Alembic migrations |
| Auth (web) | NextAuth.js v5 (Auth.js) with Discord provider |
| Auth (API) | NextAuth JWT verification using public keys / shared `NEXTAUTH_SECRET` |
| Bot integration | HTTP contract (existing bot signs webhooks with `API_INTERNAL_SECRET`) |
| Event bus | Internal Asyncio PubSub + optional Redis pub/sub (same Redis container) |
| Containerization | Docker + Docker Compose |
| Component library | Radix UI primitives + Tailwind CSS (shared via `@bnb/ui` with Shadcn) |

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

### 0.1 Initialize the Bun Monorepo (Frontend & Shared UI)
Initialize Bun at the monorepo root to orchestrate the Next.js app and TypeScript package workspaces:
```bash
bun init -y
```

Configure `package.json` to configure the TypeScript/Next.js workspaces:
```json
{
  "name": "bnb-motherboard",
  "private": true,
  "workspaces": [
    "apps/web",
    "packages/ui",
    "plugins/*"
  ],
  "scripts": {
    "dev": "turbo run dev",
    "build": "turbo run build",
    "typecheck": "turbo run typecheck",
    "lint": "turbo run lint"
  }
}
```

Install Turborepo locally:
```bash
bun add -D turbo
```

Configure `turbo.json`:
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
    "lint": {}
  }
}
```

### 0.2 Initialize the Python / uv Workspace (Backend)
Set up the `apps/api` directory as an independent Python package managed by `uv`:
```bash
cd apps/api
uv init --app app
```

This creates a `pyproject.toml` in `apps/api/`. Add the required python dependencies:
```toml
[project]
name = "bnb-api"
version = "0.1.0"
description = "FastAPI backend core for the bnb-motherboard platform"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.111.0",
    "uvicorn[standard]>=0.30.1",
    "pydantic[email]>=2.7.4",
    "pydantic-settings>=2.3.4",
    "sqlalchemy[asyncio]>=2.0.31",
    "asyncpg>=0.29.0",
    "alembic>=1.13.1",
    "python-jose[cryptography]>=3.3.0",
    "httpx>=0.27.0",
    "redis>=5.0.6",
    "apscheduler>=3.10.4",
]
```

### 0.3 Docker Compose configuration
Create a central `docker-compose.yml` in the root mapping the services:
```yaml
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
      DATABASE_URL: postgresql+asyncpg://bnb:${POSTGRES_PASSWORD:-changeme}@postgres:5432/motherboard
    ports:
      - "8000:8000"
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
      API_URL: http://api:8000
    ports:
      - "3000:3000"
    depends_on:
      - api

volumes:
  postgres_data:
```

***

## Phase 1 — Database Schema (`apps/api/app/db`)

Backend database logic is mapped using **SQLAlchemy 2.0 declarative tables** with type annotations. Asyncpg serves as the async driver.

### 1.1 ORM Table Definitions

Create `apps/api/app/db/models.py`. 13 ORM tables with full `Mapped[]` type annotations, `relationship()` with cascades, composite indexes, and JSONB columns:

```python
# Abbreviated — see apps/api/app/db/models.py for the full implementation.
# Tables: users, discord_accounts, groups, memberships, discord_role_mappings,
#         permissions, grants, delegations, forks, fork_members, plugin_registry,
#         audit_log, sync_runs
# Key fields beyond the base spec:
#   Group:              slug (unique), color_hex
#   DiscordAccount:     global_name, discord_id (String(25))
#   DiscordRoleMapping: priority (Integer), discord_role_id (String(25))
#   Permission:         key (String(150)), relationships to grants + delegations
#   Grant:              permission_key (String(150)), composite index ix_grants_principal
#   Delegation:         permission_key (String(150)), is_revoked (Boolean)
#   AuditLog:           action (String(150)), ip_address, plugin_id, indexes on created_at + action
#   PluginRegistry:     updated_at
#   Fork:               slug (unique), city_name, discord_city_role_id, discord_contributor_role_id,
#                       is_active, metadata_json (JSONB)
#   ForkMember:         track, local_role, is_active, joined_at, left_at
#   SyncRun:            trigger, status, started_at, finished_at, members_synced,
#                       members_added, members_removed, errors (JSONB), discord_member_count
```

### 1.2 Alembic Setup and Migrations
Initialize Alembic inside `apps/api/`:
```bash
uv run alembic init alembic
```

Modify `alembic/env.py` to point to the base metadata:
```python
from app.db.models import Base
target_metadata = Base.metadata
```

Generate migrations:
```bash
uv run alembic revision --autogenerate -m "initial schema"
uv run alembic upgrade head
```

***

## Phase 2 — IAM Module (`apps/api/app/iam`)

The IAM module evaluates user/group permissions using async session engines.

### 2.1 Principal Resolution
Create `apps/api/app/iam/principal.py`:
```python
import uuid
from typing import List
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import User, Membership

class ResolvedPrincipal(BaseModel):
    user_id: uuid.UUID
    group_ids: List[uuid.UUID]
    is_super_admin: bool

async def resolve_principal(db: AsyncSession, user_id: uuid.UUID) -> ResolvedPrincipal:
    user_stmt = select(User).where(User.id == user_id)
    user_res = await db.execute(user_stmt)
    user = user_res.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise ValueError("User not found or deactivated")
        
    membership_stmt = select(Membership.group_id).where(Membership.user_id == user_id)
    membership_res = await db.execute(membership_stmt)
    group_ids = list(membership_res.scalars().all())
    
    return ResolvedPrincipal(
        user_id=user.id,
        group_ids=group_ids,
        is_super_admin=user.is_super_admin
    )
```

### 2.2 Policy Evaluator
Create `apps/api/app/iam/policy.py`:
```python
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, and_, or_, is_
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Grant
from .principal import ResolvedPrincipal

async def can(
    db: AsyncSession,
    principal: ResolvedPrincipal,
    permission_key: str,
    resource_scope: Optional[str] = None
) -> bool:
    if principal.is_super_admin:
        return True
        
    now = datetime.now(timezone.utc)
    
    # User-direct or group-level grants conditions
    principal_conditions = [
        and_(Grant.principal_type == "user", Grant.principal_id == principal.user_id)
    ]
    if principal.group_ids:
        principal_conditions.append(
            and_(Grant.principal_type == "group", Grant.principal_id.in_(principal.group_ids))
        )
        
    grant_filter = and_(
        or_(*principal_conditions),
        Grant.permission_key == permission_key,
        or_(is_(Grant.expires_at, None), Grant.expires_at > now)
    )
    
    stmt = select(Grant).where(grant_filter)
    res = await db.execute(stmt)
    matching_grants = res.scalars().all()
    
    if not matching_grants:
        return False
        
    if not resource_scope:
        return True
        
    # Grant matches if it has a null resource_scope (global wildcard) or matches exactly
    return any(g.resource_scope is None or g.resource_scope == resource_scope for g in matching_grants)
```

### 2.3 System Groups Seeds
Create `apps/api/app/iam/constants.py`:
```python
SYSTEM_GROUPS = {
    "SUPER_ADMIN": "sg_super_admin",
    "STAFF": "sg_staff",
    "FORK_LEAD": "sg_fork_lead",
    "CONTRIBUTOR": "sg_contributor",
    "MEMBER": "sg_member"
}
```

***

## Phase 3 — Event Bus (`apps/api/app/events`)

The internal events module handles async signaling between modules, with an optional Redis Pub/Sub backend for multi-instance deployments.

### 3.1 Typed Event Schemas
Create `apps/api/app/events/types.py`:
```python
from typing import Any, Dict, Literal, Union
from pydantic import BaseModel

class UserCreatedPayload(BaseModel):
    user_id: str

class GroupMemberAddedPayload(BaseModel):
    user_id: str
    group_id: str
    source: str

class DiscordSyncCompletedPayload(BaseModel):
    synced_count: int
    errors: list[str]

class Event(BaseModel):
    type: Literal["user.created", "group.member.added", "discord.sync.completed"]
    payload: Dict[str, Any]
```

### 3.2 Event Bus Implementation
Create `apps/api/app/events/bus.py`:
```python
import asyncio
import json
import logging
from typing import Any, Callable, Coroutine, Dict, List, Optional
import redis.asyncio as aioredis

logger = logging.getLogger("event_bus")

class EventBus:
    def __init__(self, redis_url: Optional[str] = None):
        self._listeners: Dict[str, List[Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]]] = {}
        self.redis_url = redis_url
        self.redis: Optional[aioredis.Redis] = None
        self._pubsub_task: Optional[asyncio.Task] = None

    async def start(self):
        if self.redis_url:
            self.redis = aioredis.from_url(self.redis_url, decode_responses=True)
            self._pubsub_task = asyncio.create_task(self._redis_listener())

    async def _redis_listener(self):
        pubsub = self.redis.pubsub()
        await pubsub.subscribe("motherboard_events")
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await self._trigger_local(data["type"], data["payload"])

    def subscribe(self, event_type: str, callback: Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]):
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)

    async def publish(self, event_type: str, payload: Dict[str, Any]):
        event_data = {"type": event_type, "payload": payload}
        # Trigger local execution
        await self._trigger_local(event_type, payload)
        # Push to Redis for cross-node instances
        if self.redis:
            await self.redis.publish("motherboard_events", json.dumps(event_data))

    async def _trigger_local(self, event_type: str, payload: Dict[str, Any]):
        callbacks = self._listeners.get(event_type, [])
        for cb in callbacks:
            try:
                asyncio.create_task(cb(payload))
            except Exception as e:
                logger.error(f"Error executing subscriber callback for {event_type}: {e}")

event_bus = EventBus()
```

***

## Phase 4 — Plugin SDK (`apps/api/app/plugin_sdk`)

The plugin platform allows Python packages to register routes and logic with the motherboard backend, while their React counterparts are loaded by the Next.js shell.

### 4.1 Plugin Lifecycle Contracts
Create `apps/api/app/plugin_sdk/types.py`:
```python
from typing import Any, Callable, Coroutine, Dict, List, Literal, Optional
from fastapi import APIRouter, FastAPI
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

class PluginContext(BaseModel):
    plugin_id: str
    db_session: AsyncSession
    
    # Core system wrappers
    audit: Callable[[str, str, str, Dict[str, Any]], Coroutine[Any, Any, None]]
    publish_event: Callable[[str, Dict[str, Any]], Coroutine[Any, Any, None]]
    
    model_config = {"arbitrary_types_allowed": True}

class PermissionDeclaration(BaseModel):
    key: str
    description: str

class UiPanelDeclaration(BaseModel):
    id: str
    title: str
    route_segment: str
    placement: Literal["sidebar", "modal", "embedded"]
    required_permission: Optional[str] = None
    icon: str

class PluginManifest(BaseModel):
    id: str
    name: str
    version: str
    description: Optional[str] = None
    
    # Router instances to mount under /api/plugins/<plugin_id>
    router: Optional[APIRouter] = None
    
    # Lifecycle hooks
    on_load: Optional[Callable[[FastAPI, PluginContext], Coroutine[Any, Any, None]]] = None
    on_unload: Optional[Callable[[PluginContext], Coroutine[Any, Any, None]]] = None
    
    permissions: List[PermissionDeclaration] = []
    ui_panels: List[UiPanelDeclaration] = []
    
    model_config = {"arbitrary_types_allowed": True}
```

### 4.2 Dynamic Plugin Loader
The loader dynamically checks the `plugins/` directory, adds the directory to `sys.path`, loads the modules dynamically, runs any database schema updates declared in migrations, and mounts their FastAPI routers:

Create `apps/api/app/plugin_sdk/loader.py`:
```python
import importlib
import sys
from pathlib import Path
from typing import Dict, Any
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from .types import PluginManifest, PluginContext

class PluginLoader:
    def __init__(self, app: FastAPI, session_factory: async_sessionmaker, plugins_dir: str = "../../plugins"):
        self.app = app
        self.session_factory = session_factory
        self.plugins_dir = Path(plugins_dir)
        self.loaded_plugins: Dict[str, PluginManifest] = {}

    async def discover_and_load(self):
        if not self.plugins_dir.exists():
            return

        for p_dir in self.plugins_dir.iterdir():
            if not p_dir.is_dir():
                continue
                
            api_path = p_dir / "api"
            if not api_path.exists():
                continue
                
            # Add plugin api to path and load dynamic package
            sys.path.insert(0, str(api_path.resolve()))
            try:
                plugin_module = importlib.import_module("main")
                manifest: PluginManifest = plugin_module.get_manifest()
                
                await self.load_plugin(manifest)
            except Exception as e:
                print(f"Failed to load plugin from {p_dir}: {e}")
            finally:
                sys.path.pop(0)

    async def load_plugin(self, manifest: PluginManifest):
        # 1. Mount Router
        if manifest.router:
            self.app.include_router(
                manifest.router,
                prefix=f"/api/plugins/{manifest.id}",
                tags=[f"plugin:{manifest.id}"]
            )
            
        # 2. Run initial tasks via on_load hook
        async with self.session_factory() as session:
            ctx = PluginContext(
                plugin_id=manifest.id,
                db_session=session,
                audit=self._make_audit_fn(manifest.id, session),
                publish_event=self._make_publish_fn()
            )
            if manifest.on_load:
                await manifest.on_load(self.app, ctx)
                
        self.loaded_plugins[manifest.id] = manifest

    def _make_audit_fn(self, plugin_id: str, session: AsyncSession):
        from app.iam.audit import write_audit_entry
        async def audit_fn(action: str, target_type: str, target_id: str, meta: Dict[str, Any]):
            await write_audit_entry(session, actor_id=None, action=f"plugin.{plugin_id}.{action}", target_type=target_type, target_id=target_id, metadata=meta)
        return audit_fn

    def _make_publish_fn(self):
        from app.events.bus import event_bus
        async def publish_fn(event_type: str, payload: Dict[str, Any]):
            await event_bus.publish(event_type, payload)
        return publish_fn
```

***

## Phase 5 — Provisioning Worker (`apps/api/app/provisioning`)

The provisioning worker fetches guild member mappings from Discord, compares them to mapped roles, and writes synchronization updates back to internal database groups.

### 5.1 Discord REST Client
Create `apps/api/app/provisioning/client.py`:
```python
from typing import Any, Dict, List
import httpx

class DiscordClient:
    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.base_url = "https://discord.com/api/v10"
        self.headers = {"Authorization": f"Bot {self.bot_token}"}

    async def get_guild_members(self, guild_id: str) -> List[Dict[str, Any]]:
        members = []
        limit = 1000
        after = "0"
        
        async with httpx.AsyncClient(base_url=self.base_url, headers=self.headers) as client:
            while True:
                resp = await client.get(
                    f"/guilds/{guild_id}/members",
                    params={"limit": limit, "after": after}
                )
                resp.raise_for_status()
                data = resp.json()
                if not data:
                    break
                members.extend(data)
                after = data[-1]["user"]["id"]
                if len(data) < limit:
                    break
        return members

    async def get_roles(self, guild_id: str) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(base_url=self.base_url, headers=self.headers) as client:
            resp = await client.get(f"/guilds/{guild_id}/roles")
            resp.raise_for_status()
            return resp.json()
```

### 5.2 Synchronization Task
Create `apps/api/app/provisioning/sync.py`:
```python
import logging
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import DiscordAccount, DiscordRoleMapping, Membership
from app.provisioning.client import DiscordClient

logger = logging.getLogger("sync_worker")

async def run_sync(db: AsyncSession, discord_client: DiscordClient, guild_id: str) -> dict:
    errors = []
    synced_count = 0
    
    try:
        # 1. Fetch Discord users and mapped database roles
        members = await discord_client.get_guild_members(guild_id)
        
        map_stmt = select(DiscordRoleMapping).where(DiscordRoleMapping.sync_enabled == True)
        map_res = await db.execute(map_stmt)
        mappings = map_res.scalars().all()
        mapping_dict = {m.discord_role_id: m.group_id for m in mappings}
        
        # 2. Iterate and sync roles
        for member in members:
            discord_id = member["user"]["id"]
            roles = member["roles"]
            
            acc_stmt = select(DiscordAccount).where(DiscordAccount.discord_id == discord_id)
            acc_res = await db.execute(acc_stmt)
            account = acc_res.scalar_one_or_none()
            
            if not account:
                continue  # User has not registered in the app dashboard yet
                
            user_id = account.user_id
            
            # Fetch current user synced memberships
            mem_stmt = select(Membership).where(
                Membership.user_id == user_id,
                Membership.source == "discord_sync"
            )
            mem_res = await db.execute(mem_stmt)
            current_mems = {m.group_id: m for m in mem_res.scalars().all()}
            
            target_group_ids = {mapping_dict[r] for r in roles if r in mapping_dict}
            
            # Add missing memberships
            for group_id in target_group_ids:
                if group_id not in current_mems:
                    new_mem = Membership(
                        user_id=user_id,
                        group_id=group_id,
                        source="discord_sync"
                    )
                    db.add(new_mem)
                    synced_count += 1
            
            # Remove stale memberships
            for group_id, membership in current_mems.items():
                if group_id not in target_group_ids:
                    await db.delete(membership)
                    synced_count += 1
                    
            account.last_synced_at = datetime.now(timezone.utc)
            
        await db.commit()
    except Exception as e:
        logger.error(f"Sync worker failed: {e}")
        errors.append(str(e))
        await db.rollback()
        
    return {"synced_count": synced_count, "errors": errors}
```

### 5.3 Scheduler Setup
Schedule the job using **APScheduler**'s AsyncIOScheduler inside `apps/api/app/main.py`'s lifespan. Run every `SYNC_INTERVAL_MINUTES` env variable (default: 15).

***

## Phase 6 — FastAPI Core API (`apps/api/app`)

Core API layout, routes, JWT security middleware, and startup lifespans.

### 6.1 Server Lifespan Configuration
Actual implementation in `apps/api/app/main.py`:
```python
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import get_engine, get_sessionmaker
from app.db.seeder import run_seeds

@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()

    # Run Alembic migrations programmatically
    import asyncio
    from alembic import command
    from alembic.config import Config as AlembicConfig

    def _run_migrations() -> None:
        alembic_cfg = AlembicConfig("alembic.ini")
        command.upgrade(alembic_cfg, "head")

    await asyncio.to_thread(_run_migrations)

    # Seed reference data
    async with get_sessionmaker()() as session:
        await run_seeds(session)

    yield
    await get_engine().dispose()

def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="bnb-motherboard API",
        version="0.1.0",
        description="Internal operations platform for the bits&bytes network.",
        lifespan=lifespan,
    )

    # CORS
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.nextauth_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers — each router defines its own prefix
    from app.routers import health, users, groups, forks, audit, sync, plugins, finance
    application.include_router(health.router)
    application.include_router(users.router)
    application.include_router(groups.router)
    application.include_router(forks.router)
    application.include_router(audit.router)
    application.include_router(sync.router)
    application.include_router(plugins.router)
    application.include_router(finance.router)

    return application

app = create_app()
```

> **Note:** The event bus, plugin loader, and provisioning scheduler (shown in the original spec) are planned for Phases 3–5 but not yet implemented in `main.py`.

### 6.2 Settings Model
Actual implementation in `apps/api/app/config.py`:
```python
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    discord_client_id: str = Field(validation_alias="DISCORD_CLIENT_ID")
    discord_client_secret: str = Field(validation_alias="DISCORD_CLIENT_SECRET")
    discord_bot_token: str = Field(validation_alias="DISCORD_BOT_TOKEN")
    discord_guild_id: str = Field(validation_alias="DISCORD_GUILD_ID")
    database_url: str = Field(validation_alias="DATABASE_URL")
    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")
    session_secret: str = Field(validation_alias="SESSION_SECRET")
    api_internal_secret: str = Field(validation_alias="API_INTERNAL_SECRET")
    nextauth_secret: str = Field(validation_alias="NEXTAUTH_SECRET")
    nextauth_url: str = Field(default="http://localhost:3000", validation_alias="NEXTAUTH_URL")
    api_url: str = Field(default="http://localhost:8000", validation_alias="API_URL")
    cors_origins: str = Field(default="", validation_alias="CORS_ORIGINS")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
```

### 6.3 Database Session & Settings Dependencies
Actual implementation in `apps/api/app/dependencies.py`:
```python
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_session


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async for session in get_session():
        yield session


# Typed dependency aliases
DbSession = Annotated[AsyncSession, Depends(get_db_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]
```

> **Note:** The `CurrentUserDep` JWT authentication dependency (shown in the original spec) is planned but not yet implemented. The IAM router currently imports `CurrentUserDep` from `app.dependencies` as a forward reference for Phase 2 integration.

***

## Phase 7 — Next.js Web App (`apps/web`)

The Next.js 15 app router manages dashboard views and handles auth callbacks with NextAuth.js.

### 7.1 NextAuth Upsert Callbacks
Actual implementation in `apps/web/lib/auth.ts`:
```typescript
import NextAuth from "next-auth";
import Discord from "next-auth/providers/discord";

export const { auth, handlers, signIn, signOut } = NextAuth({
  providers: [
    Discord({
      authorization: {
        params: {
          scope: "identify email guilds guilds.members.read",
        },
      },
    }),
  ],
  pages: {
    signIn: "/login",
  },
  callbacks: {
    async jwt({ token, account, profile }) {
      token.discordId ??= "";
      token.accessToken ??= "";
      if (account && profile) {
        token.discordId = (profile as { id: string }).id;
        token.accessToken = account.access_token ?? "";

        // Fire-and-forget upsert to backend API
        const apiUrl = process.env.API_URL;
        const internalSecret = process.env.API_INTERNAL_SECRET;

        if (apiUrl && internalSecret) {
          fetch(`${apiUrl}/api/auth/upsert`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-Internal-Secret": internalSecret,
            },
            body: JSON.stringify({
              discordId: (profile as { id: string }).id,
              email: (profile as { email?: string }).email,
              username: (profile as { username?: string }).username,
              avatar: (profile as { avatar?: string }).avatar,
              accessToken: account.access_token,
            }),
          }).catch(() => {
            // Silently ignore — never block sign-in on API failure
          });
        }
      }
      return token;
    },
    async session({ session, token }) {
      session.user.discordId = token.discordId;
      return session;
    },
  },
  secret: process.env.NEXTAUTH_SECRET,
});
```

Middleware in `apps/web/middleware.ts` protects `/dashboard(.*)` routes with a session check + redirect to `/login`.

### 7.2 UI Plugin Mounting Router
Next.js loads the frontend UI of plugin components dynamically:

Update `apps/web/app/(dashboard)/plugins/[pluginId]/[[...slug]]/page.tsx`:
```typescript
import dynamic from 'next/dynamic';
import { Skeleton } from '@bnb/ui';

export default async function PluginPage({ params }: { params: { pluginId: string } }) {
  const PluginPanel = dynamic(
    () => import(`@bnb-plugins/${params.pluginId}/ui`).catch(() => () => <div>Plugin UI panel not found</div>),
    { loading: () => <Skeleton className="h-96 w-full" />, ssr: false }
  );

  return <PluginPanel />;
}
```

***

## Phase 8 — Shared UI Package (`packages/ui`)

The UI components library is a Turborepo-managed workspace exporting custom components styled using **Tailwind CSS and Radix UI Primitives (Shadcn layout styling)**. 

Components must include:
*   `Button`, `Input`, `Select`
*   `Dialog`, `DropdownMenu`
*   `Table`, `Badge` (success, warning, error, info)
*   `Card`, `Skeleton`

Consuming apps configure Tailwind CSS paths to index the shared module classes automatically:
```ts
// tailwind.config.js
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx}",
    "../../packages/ui/src/**/*.{js,ts,jsx,tsx}"
  ],
  // ...
}
```

***

## Phase 9 — Discord Role Mapping UI

The administrative dashboard allows users to bind Discord guild roles to operational groups dynamically.

1.  Renders a matrix of Discord roles fetched via `GET /api/iam/discord-roles`.
2.  Allows selection of internal groups fetched via `GET /api/iam/groups`.
3.  Saves updates directly by invoking `PUT /api/iam/discord-mappings` (upsert updates).
4.  Displays blocking spinners during processing. No optimistic updates.

***

## Phase 10 — Dockerfiles and Production Compose

Docker files configured to support optimized production builds.

### 10.1 API Dockerfile (`docker/api.Dockerfile`)
Actual implementation using `python:3.12-slim` with `uv` installed via pip:
```dockerfile
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY apps/api/pyproject.toml apps/api/uv.lock ./
COPY apps/api/README.md ./README.md
COPY apps/api/app ./app

RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.12-slim AS runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/pyproject.toml /app/pyproject.toml
COPY --from=builder /app/uv.lock /app/uv.lock
COPY --from=builder /app/README.md /app/README.md
COPY --from=builder /app/app /app/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

> **Note:** Alembic migrations run programmatically in `main.py`'s lifespan on startup, so no separate `alembic` or `migrate` service is needed.

### 10.2 Web Dockerfile (`docker/web.Dockerfile`)
Actual implementation using `bun:1.3.11-alpine`:
```dockerfile
FROM oven/bun:1.3.11-alpine AS base

WORKDIR /app

COPY package.json bun.lock turbo.json tsconfig.base.json tsconfig.json ./
COPY apps/web ./apps/web
COPY packages/ui ./packages/ui

RUN bun install --frozen-lockfile

FROM base AS builder

WORKDIR /app/apps/web

RUN bun run build

FROM oven/bun:1.3.11-alpine AS runner

ENV NODE_ENV=production

WORKDIR /app

COPY --from=base /app/node_modules ./node_modules
COPY --from=base /app/package.json ./package.json
COPY --from=base /app/bun.lock ./bun.lock
COPY --from=base /app/apps/web ./apps/web
COPY --from=base /app/packages/ui ./packages/ui
COPY --from=builder /app/apps/web/.next ./apps/web/.next

EXPOSE 3000

CMD ["bun", "--cwd", "apps/web", "run", "start"]
```

### 10.3 Production Compose (`docker-compose.prod.yml`)
Actual implementation — no separate `migrate` service (migrations run in `main.py` lifespan):
```yaml
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

  redis:
    image: redis:7-alpine
    restart: unless-stopped

  api:
    build:
      context: .
      dockerfile: docker/api.Dockerfile
    restart: unless-stopped
    env_file: .env
    environment:
      DATABASE_URL: postgresql+asyncpg://bnb:${POSTGRES_PASSWORD:-changeme}@postgres:5432/motherboard
      API_URL: http://api:8000
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
      API_URL: http://api:8000
    depends_on:
      - api

volumes:
  postgres_data:
```

***

## Coding Conventions

### Backend (Python)

- **Coding Standard**: PEP 8.
- **Variable and File Names**: `snake_case`.
- **Classes**: `PascalCase`.
- **Type Annotations**: Mandatory on all function arguments and return signatures.
- **Route Definitions**: Use `Annotated` dependencies (e.g. `db: DbDep`) and explicit `response_model` definitions on every route.
- **Async Execution**: Use async handlers only for non-blocking I/O operations (HTTPX client calls, SQLAlchemy async executions). Use plain blocking `def` functions for code that is CPU-bound or blocking (runs in ThreadPool).
- **Unit Testing**: pytest with `httpx.AsyncClient` transport wrappers for route isolation.

### Frontend (Next.js & TypeScript)

- **Variables and Functions**: `camelCase`.
- **Files**: `kebab-case.ts`.
- **Components**: `PascalCase` matching file names exactly.
- **Type Checking**: Enforced strict null checks, no `as any` type-escaping.
- **Linting**: ESLint + Prettier.

***

## Definition of Done (Per Phase)

Each phase is complete when:

- [ ] All TypeScript compiles successfully without errors (`bun run typecheck`).
- [ ] Backend codebase linting/typechecking succeeds.
- [ ] No `any` annotations exist in TypeScript or untyped parameters in Python.
- [ ] Input parameters validate against strictly mapped Pydantic/Zod schemas.
- [ ] Tests execute successfully with zero failures.
- [ ] App logs clean executions upon invoking `docker compose up`.
