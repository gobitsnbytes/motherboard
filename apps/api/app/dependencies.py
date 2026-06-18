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


async def get_db_session(session: AsyncSession = Depends(get_session)) -> AsyncIterator[AsyncSession]:
    yield session


# ---------------------------------------------------------------------------
# Typed dependency aliases
# ---------------------------------------------------------------------------

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]

DbDep = DbSession

from fastapi import Header, HTTPException, status
from app.iam.principal import ResolvedPrincipal, resolve_principal
import uuid

async def get_current_user(
    db: DbSession,
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None
) -> ResolvedPrincipal:
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-User-Id header"
        )
    try:
        user_uuid = uuid.UUID(x_user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid X-User-Id format"
        )
    try:
        return await resolve_principal(db, user_uuid)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )

CurrentUserDep = Annotated[ResolvedPrincipal, Depends(get_current_user)]

