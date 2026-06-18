# bnb-api

FastAPI backend for the bnb-motherboard platform — the internal operations API for the bits&bytes network.

## Technology Stack

- **Runtime:** Python 3.12
- **Framework:** FastAPI 0.111+ with Pydantic v2 schemas
- **ORM:** SQLAlchemy 2.0 (async, asyncpg driver)
- **Migrations:** Alembic (auto-migrate on startup)
- **Package Manager:** uv (Astral)

## Module Structure

```
app/
├── main.py            # Application factory, lifespan, CORS, router registration
├── config.py          # Pydantic Settings (env vars via Field validation_alias)
├── database.py        # Async engine + sessionmaker
├── dependencies.py    # DbSession / AppSettings typed dependency aliases
├── db/                # ORM models (13 tables), seeder, seed data
├── iam/               # Principal resolver, policy evaluator (can/require_permission/batch_can), audit writer
├── events/            # Event bus (placeholder — Phase 3)
├── provisioning/      # Discord sync worker (placeholder — Phase 5)
├── plugin_sdk/        # Plugin loader (placeholder — Phase 4)
├── routers/           # API route handlers (8 registered in main.py)
│   ├── health.py      # GET /health/
│   ├── users.py       # /api/users/*
│   ├── groups.py      # /api/groups/*
│   ├── forks.py       # /api/forks/*
│   ├── audit.py       # /api/audit/*
│   ├── sync.py        # /api/sync/*
│   ├── plugins.py     # /api/plugins/*
│   ├── finance.py     # /api/finance/* (health + info)
│   └── iam.py         # /me, /permissions, /grants, /groups, /discord-roles, /discord-mappings (not yet registered in main.py)
└── schemas/           # Pydantic v2 request/response schemas
```

## Quick Start

```bash
# Install dependencies
uv sync

# Run development server
uv run uvicorn app.main:app --reload --port 8000

# Run Alembic migrations manually
uv run alembic upgrade head

# Create a new migration
uv run alembic revision --autogenerate -m "description"

# Run tests
uv run pytest
```

## Environment Variables

All secrets are loaded via `app/config.py` using Pydantic Settings with `Field(validation_alias=...)`. See root `.env.example` for the full list.
