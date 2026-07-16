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
    # 1. API Key Auth Fallback
    api_key = request.headers.get("x-api-key")
    if not api_key:
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.strip().startswith("Bearer "):
            api_key = auth_header.split("Bearer ", 1)[1].strip()

    if api_key:
        settings = get_settings()
        expected_api_key = settings.api_internal_secret
        if hmac.compare_digest(api_key, expected_api_key):
            from sqlalchemy import select
            from app.db.models import User
            res = await db.execute(select(User).where(User.is_super_admin == True).limit(1))
            sys_user = res.scalar_one_or_none()
            if sys_user:
                return await resolve_principal(db, sys_user.id)
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="No super admin user found to bind system context"
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API Key"
            )

    # 2. Next.js internal auth headers
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

    user_uuid = None
    if x_internal_user_id in ("system", "discord_bot"):
        from sqlalchemy import select
        from app.db.models import User
        res = await db.execute(select(User).where(User.is_super_admin == True).limit(1))
        sys_user = res.scalar_one_or_none()
        if sys_user:
            user_uuid = sys_user.id
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No super admin user found to bind system context"
            )
    else:
        try:
            user_uuid = uuid.UUID(x_internal_user_id)
        except ValueError:
            # Try to resolve via Discord Account ID if it is a digit-only snowflake
            if x_internal_user_id.isdigit():
                from sqlalchemy import select
                from app.db.models import DiscordAccount
                res = await db.execute(select(DiscordAccount).where(DiscordAccount.discord_id == x_internal_user_id))
                acc = res.scalar_one_or_none()
                if acc:
                    user_uuid = acc.user_id
                else:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail=f"No local user found linked to Discord ID: {x_internal_user_id}"
                    )
            else:
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

