"""
FastAPI dependency injectors.

Exports typed aliases for common dependencies so route functions stay concise:

    async def my_route(db: DbSession, settings: AppSettings) -> ...:
"""

from collections.abc import AsyncIterator
import hashlib
import hmac
import time
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
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

from app.iam.principal import ResolvedPrincipal, resolve_principal
import uuid

INTERNAL_AUTH_MAX_AGE_SECONDS = 300


def canonical_auth_path(path: str) -> str:
    """Normalize paths for internal request signatures."""
    return path.rstrip("/") or "/"


def sign_internal_auth(
    *,
    secret: str,
    timestamp: str,
    method: str,
    path: str,
    user_id: str,
) -> str:
    """Return the HMAC signature used by the trusted Next.js API proxy."""
    message = f"{timestamp}{method.upper()}{canonical_auth_path(path)}{user_id}"
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


async def get_current_user(
    request: Request,
    db: DbSession,
    x_internal_user_id: Annotated[str | None, Header(alias="X-Internal-User-Id")] = None,
    x_internal_timestamp: Annotated[str | None, Header(alias="X-Internal-Timestamp")] = None,
    x_internal_signature: Annotated[str | None, Header(alias="X-Internal-Signature")] = None,
) -> ResolvedPrincipal:
    if not x_internal_user_id or not x_internal_timestamp or not x_internal_signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing internal authentication headers"
        )

    try:
        timestamp_value = int(x_internal_timestamp)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal authentication timestamp",
        )

    if abs(int(time.time()) - timestamp_value) > INTERNAL_AUTH_MAX_AGE_SECONDS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Stale internal authentication timestamp",
        )

    settings = get_settings()
    expected_signature = sign_internal_auth(
        secret=settings.api_internal_secret,
        timestamp=x_internal_timestamp,
        method=request.method,
        path=request.url.path,
        user_id=x_internal_user_id,
    )
    if not hmac.compare_digest(expected_signature, x_internal_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal authentication signature",
        )

    try:
        user_uuid = uuid.UUID(x_internal_user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid internal user id format"
        )
    try:
        return await resolve_principal(db, user_uuid)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )

CurrentUserDep = Annotated[ResolvedPrincipal, Depends(get_current_user)]

