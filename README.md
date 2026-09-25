# Motherboard

[![API](https://github.com/gobitsnbytes/motherboard/actions/workflows/deploy-api.yml/badge.svg?branch=prod)](https://github.com/gobitsnbytes/motherboard/actions/workflows/deploy-api.yml)
[![Web](https://github.com/gobitsnbytes/motherboard/actions/workflows/web-ci.yml/badge.svg?branch=prod)](https://github.com/gobitsnbytes/motherboard/actions/workflows/web-ci.yml)

The internal operations platform for the Bits&Bytes network (GOBITSNBYTES Foundation). It covers identity and access, Discord sync, finance, onboarding, legal documents, and forms.

## Stack

| Path | What | Tooling |
|---|---|---|
| `apps/web` | Next.js 15 App Router dashboard (React 19) | Bun |
| `apps/api` | FastAPI + SQLAlchemy 2 async + Alembic | uv / Python 3.12 |
| `apps/bot` | Discord bot and scheduled jobs | Bun |
| `packages/ui` | Shared React components | Bun |
| `plugins/*` | Plugin packages (API + UI) | Bun / Python |
| `deploy/`, `docker/` | VPS deploy scripts and Dockerfiles | |

Errors, traces, and cron check-ins go to Sentry. See [docs/observability.md](docs/observability.md).

## Local setup

```bash
bun install
cp .env.example .env
docker compose up -d postgres redis

# API → http://localhost:8000 (docs at /api/docs)
cd apps/api && uv sync && uv run uvicorn app.main:app --reload --port 8000

# Web → http://localhost:3000
bun run dev --filter=web
```

## Tests

```bash
cd apps/api && uv run pytest -n auto   # backend
bun test --cwd apps/bot                # bot
bun test --cwd apps/web                # web
```

## Deploy

Pushing to `prod` deploys the API and bot to the VPS through [deploy-api.yml](.github/workflows/deploy-api.yml), and deploys the web app on Vercel. Contributor workflow and conventions live in [AGENTS.md](AGENTS.md).
