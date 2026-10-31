"""Trusted auth bridge used by the NextAuth frontend."""

from __future__ import annotations

import hmac
import logging
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.db.models import DiscordAccount, User
from app.dependencies import DbSession
from app.provisioning.client import fetch_own_guild_roles
from app.provisioning.sync import sync_member_roles
from app.schemas.auth import DiscordUpsertRequest, DiscordUpsertResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


def _avatar_url(discord_id: str, avatar_hash: str | None) -> str | None:
    if not avatar_hash:
        return None
    if avatar_hash.startswith("http://") or avatar_hash.startswith("https://"):
        return avatar_hash
    return f"https://cdn.discordapp.com/avatars/{discord_id}/{avatar_hash}.png"


def _display_name(payload: DiscordUpsertRequest) -> str:
    return payload.global_name or payload.username or payload.email or f"Discord {payload.discord_id}"


@router.post("/upsert", response_model=DiscordUpsertResponse)
async def upsert_discord_identity(
    payload: DiscordUpsertRequest,
    db: DbSession,
    x_internal_secret: Annotated[str | None, Header(alias="X-Internal-Secret")] = None,
) -> DiscordUpsertResponse:
    settings = get_settings()
    if not x_internal_secret or not hmac.compare_digest(
        x_internal_secret,
        settings.api_internal_secret,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal secret",
        )

    result = await db.execute(
        select(DiscordAccount).where(DiscordAccount.discord_id == payload.discord_id)
    )
    discord_account = result.scalar_one_or_none()

    if discord_account:
        user = await db.get(User, discord_account.user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Discord account is linked to a missing user",
            )
    else:
        user = User(
            display_name=_display_name(payload),
            email=payload.email,
            avatar_url=_avatar_url(payload.discord_id, payload.avatar),
            is_super_admin=False,
        )
        db.add(user)
        await db.flush()
        discord_account = DiscordAccount(
            user_id=user.id,
            discord_id=payload.discord_id,
            username=payload.username or payload.discord_id,
        )
        db.add(discord_account)

    if not user.profile_completed:
        user.display_name = _display_name(payload)
        user.email = payload.email
    user.avatar_url = _avatar_url(payload.discord_id, payload.avatar)
    discord_account.username = payload.username or discord_account.username
    discord_account.global_name = payload.global_name
    discord_account.avatar_hash = payload.avatar
    discord_account.access_token = payload.access_token

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Discord identity conflicts with an existing user",
        ) from exc

    # Resolve Discord roles now. Without this a new member signs in with no access until the next
    # sweep. A Discord outage must never block sign-in, so failure keeps whatever access they have.
    if payload.access_token and settings.discord_guild_id:
        try:
            roles = await fetch_own_guild_roles(payload.access_token, settings.discord_guild_id)
            await sync_member_roles(db, payload.discord_id, roles)
        except Exception:
            logger.warning("Sign-in role sync skipped for discord_id=%s", payload.discord_id, exc_info=True)

    return DiscordUpsertResponse(user_id=user.id)
