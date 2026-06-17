"""
FastAPI dependency injectors.

Exports typed aliases for common dependencies so route functions stay concise:

    async def my_route(db: DbSession, settings: AppSettings) -> ...:
"""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_session


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async for session in get_session():
        yield session


# ---------------------------------------------------------------------------
# Typed dependency aliases
# ---------------------------------------------------------------------------

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]
