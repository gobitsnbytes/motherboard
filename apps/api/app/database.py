import os
import logging
from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

logger = logging.getLogger(__name__)

SQLITE_FALLBACK_URL = "sqlite+aiosqlite:///data/motherboard.db"


def engine_options(url: str) -> dict:
    """Pool and timeout limits sized for the 1 GB / 1 vCPU host.

    Two API workers overlap during a blue/green rollout, so 5+2 connections each
    stays well under Postgres' default 100 and keeps memory flat. A request that
    cannot get a connection in 10s fails with a clear 5xx instead of hanging until
    the web proxy gives up.
    """
    options: dict = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        return options
    options.update(pool_size=5, max_overflow=2, pool_timeout=10, pool_recycle=1800)
    if url.startswith("postgresql+asyncpg"):
        options["connect_args"] = {
            "command_timeout": 30,
            "server_settings": {
                "statement_timeout": "30000",
                "idle_in_transaction_session_timeout": "60000",
            },
        }
    return options


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    settings = get_settings()
    db_url = settings.database_url

    # Check if forced to SQLite fallback via env var or file
    if os.environ.get("USE_LOCAL_SQLITE", "false").lower() in ("true", "1"):
        logger.info("Using local SQLite database: %s", SQLITE_FALLBACK_URL)
        os.makedirs("data", exist_ok=True)
        return create_async_engine(SQLITE_FALLBACK_URL, pool_pre_ping=True)

    return create_async_engine(db_url, **engine_options(db_url))


def get_sqlite_engine() -> AsyncEngine:
    os.makedirs("data", exist_ok=True)
    return create_async_engine(SQLITE_FALLBACK_URL, pool_pre_ping=True)


@lru_cache(maxsize=1)
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as session:
        yield session


def clear_db_cache() -> None:
    """Clear the cached DB engine and sessionmaker (for testing)."""
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
