import os
import logging
from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

logger = logging.getLogger(__name__)

SQLITE_FALLBACK_URL = "sqlite+aiosqlite:///data/motherboard.db"


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    settings = get_settings()
    db_url = settings.database_url

    # Check if forced to SQLite fallback via env var or file
    if os.environ.get("USE_LOCAL_SQLITE", "false").lower() in ("true", "1"):
        logger.info("Using local SQLite database: %s", SQLITE_FALLBACK_URL)
        os.makedirs("data", exist_ok=True)
        return create_async_engine(SQLITE_FALLBACK_URL, pool_pre_ping=True)

    return create_async_engine(db_url, pool_pre_ping=True)


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
