"""
Alembic environment configuration for bnb-motherboard.

Uses SQLAlchemy 2.0 async engine (asyncpg driver) via a sync wrapper
that Alembic can run in its synchronous migration context.
"""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

# Import all ORM models so Alembic's autogenerate can detect them.
# This must happen BEFORE accessing Base.metadata.
from app.db.models import Base  # noqa: F401 — side-effect import registers all tables

# ---------------------------------------------------------------------------
# Alembic Config object
# ---------------------------------------------------------------------------

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# Resolve DATABASE_URL at runtime (reads from environment or .env)
# ---------------------------------------------------------------------------


def get_database_url() -> str:
    """Read DATABASE_URL from the environment, falling back to alembic.ini."""
    url = os.environ.get("DATABASE_URL") or config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError("DATABASE_URL is not set. Cannot run migrations.")
    return url


# ---------------------------------------------------------------------------
# Offline migrations (generates SQL script without a live DB connection)
# ---------------------------------------------------------------------------


def run_migrations_offline() -> None:
    """Run migrations without a live database connection (emit SQL to stdout)."""
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online migrations (connects to the live database)
# ---------------------------------------------------------------------------


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    url = get_database_url()
    connectable = create_async_engine(
        url,
        poolclass=pool.NullPool,  # Use NullPool for migration — don't hold connections
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
