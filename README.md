# bnb-motherboard

internal operations platform and core monorepo for the bits&bytes network (GOBITSNBYTES FOUNDATION).

the repository is a hybrid monorepo:
- `apps/web` & `packages/ui` are Bun/pnpm-managed Next.js 15 TypeScript workspaces.
- `apps/api` is an independent Python FastAPI backend managed via `uv`.
- `plugins/*` holds internal extension packages and integrations.

---

## Core Capabilities

- **IAM Engine**: custom principal resolver and policy evaluator (`can`, `require_permission`, `batch_can`) backed by async SQLAlchemy & non-committing audit logs.
- **Discord OAuth & Guild Sync**: Discord-backed identity management, automated guild role mapping, and member sync.
- **Finance & Banking Ledger**: RazorpayX ledger and banking integration for section 8 compliance (`apps/api/app/routers/finance.py` & `apps/web/app/finance`).
- **Dashboard**: Next.js 15 App Router frontend connected to FastAPI via REST and WebSockets.
- **Orchestration**: Docker Compose setup for local development and production environments.

---

## Repository Layout

```text
bnb-motherboard/
├── apps/
│   ├── web/                    # Next.js 15 App Router dashboard
│   └── api/                    # FastAPI REST API managed with uv
├── packages/
│   └── ui/                     # Shared React component library
├── plugins/                    # Extension packages
├── docker/                     # Service Dockerfiles
├── docker-compose.yml          # Local orchestration
├── docker-compose.prod.yml     # Production orchestration
└── AGENTS.md                   # Workspace instructions & team roles
```

---

## Local Setup

```bash
# 1. install dependencies
bun install

# 2. setup environment secrets
cp .env.example .env

# 3. start local infrastructure (PostgreSQL + Redis)
docker compose up -d postgres redis

# 4. start FastAPI backend
cd apps/api
uv sync
uv run uvicorn app.main:app --reload --port 8000

# 5. start Next.js dashboard
bun run dev --filter=web
```

---

## Docker Deployment

```bash
# dev full stack
docker compose up --build -d

# production stack (isolated ports)
docker compose -f docker-compose.prod.yml up --build -d
```

| Service | URL | Description |
|---|---|---|
| **Web** | `http://localhost:3000` | Next.js frontend |
| **API** | `http://localhost:8000` | FastAPI REST API |
| **Docs** | `http://localhost:8000/api/docs` | Swagger UI OpenAPI docs |
