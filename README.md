# bnb-motherboard

Internal operations platform for the bits&bytes network.

The repo is a hybrid monorepo:

- `apps/web` and `packages/ui` are Bun-managed TypeScript workspaces.
- `apps/api` is an independent Python FastAPI project managed by `uv`.
- `plugins/*` holds first-party and third-party plugin packages.

## What It Covers

- Discord-backed identity and access management.
- Provisioning and sync for guild roles and internal memberships.
- Plugin loading and extension points.
- **Finance & Ledger** — Ledger + Banking system for GOBITSNBYTES FOUNDATION powered by [RazorpayX](https://razorpay.com/x/) API. Frontend at `/finance`, backend at `/api/finance/*`.
- A Next.js 15 dashboard backed by a FastAPI REST API.
- Docker-based local and production deployment.

## Repository Layout

```text
bnb-motherboard/
├── apps/
│   ├── web/                    # Next.js 15 App Router frontend
│   └── api/                    # FastAPI backend managed with uv
├── packages/
│   └── ui/                     # Shared React component library
├── plugins/                    # First-party plugin workspace
├── docker/                     # Service Dockerfiles
├── docker-compose.yml          # Local orchestration
├── docker-compose.prod.yml     # Production orchestration
├── .env.example                # Environment template
├── turbo.json                  # Bun/Turborepo task graph
└── AGENTS.md                   # Workspace instructions
```

## Local Setup

```bash
# 1. Install JS/TS dependencies
bun install

# 2. Copy env and fill in secrets
copy .env.example .env

# 3. Start infrastructure (Postgres + Redis)
docker compose up -d postgres redis

# 4. Start the FastAPI backend (in a separate terminal)
cd apps/api
uv sync
uv run uvicorn app.main:app --reload --port 8000

# 5. Start the Next.js frontend (in a separate terminal)
bun run dev --filter=web
```

## Docker — Full Stack

```bash
# Build and run everything (Postgres, Redis, API, Web)
docker compose up --build -d

# Production mode (no exposed DB/Redis ports)
docker compose -f docker-compose.prod.yml up --build -d
```

| Service | URL | Description |
|---------|-----|-------------|
| **Web (Next.js)** | `http://localhost:3000` | Frontend dashboard |
| **API (FastAPI)** | `http://localhost:8000` | Backend REST API |
| **API Docs** | `http://localhost:8000/api/docs` | Swagger UI (auto-generated) |
| **Postgres** | `localhost:5432` | Database (dev only) |
| **Redis** | `localhost:6379` | Cache / event bus (dev only) |

## Environment

Copy [.env.example](.env.example) to `.env` and fill in the Discord OAuth, session, and API secrets.
