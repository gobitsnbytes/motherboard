"""Users router — CRUD for internal user records."""

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.models import DiscordAccount, Membership, User
from app.dependencies import CurrentUserDep, DbSession
from app.iam.policy import require_permission
from app.schemas.users import (
    MemberDirectoryOut,
    MemberRoleOut,
    UserCreate,
    UserOut,
    UserUpdate,
)

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def get_current_user_profile(
    db: DbSession,
    current_user: CurrentUserDep,
) -> User:
    return await db.get(User, current_user.user_id)


@router.patch("/me", response_model=UserOut)
async def update_current_user_profile(
    payload: UserUpdate,
    db: DbSession,
    current_user: CurrentUserDep,
) -> User:
    user = await db.get(User, current_user.user_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "is_super_admin":
            continue
        setattr(user, field, value)
    user.profile_completed = True
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/", response_model=list[UserOut])
async def list_users(db: DbSession, current_user: CurrentUserDep) -> list[User]:
    await require_permission(db, current_user, "iam.users.read")
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return list(result.scalars().all())


@router.get("/members", response_model=list[MemberDirectoryOut])
async def list_members(
    db: DbSession, current_user: CurrentUserDep
) -> list[MemberDirectoryOut]:
    """Return active people who have authenticated with Discord."""
    await require_permission(db, current_user, "iam.users.read")
    result = await db.execute(
        select(User)
        .join(DiscordAccount)
        .options(
            selectinload(User.discord_account),
            selectinload(User.memberships).selectinload(Membership.group),
        )
        .where(User.is_active.is_(True))
        .order_by(User.display_name)
    )
    now = datetime.now(timezone.utc)
    members = []
    for user in result.scalars():
        account = user.discord_account
        roles = [
            MemberRoleOut(
                slug=membership.group.slug,
                name=membership.group.name,
                color_hex=membership.group.color_hex,
            )
            for membership in user.memberships
            if membership.source == "discord_sync"
            and (
                membership.expires_at is None
                or membership.expires_at.replace(tzinfo=timezone.utc) > now
            )
        ]
        members.append(
            MemberDirectoryOut(
                id=user.id,
                display_name=user.display_name,
                email=user.email,
                title=user.title,
                avatar_url=user.avatar_url,
                discord_id=account.discord_id,
                discord_username=account.username,
                last_synced_at=account.last_synced_at,
                roles=sorted(roles, key=lambda role: role.name.lower()),
                created_at=user.created_at,
            )
        )
    return members


@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: Annotated[uuid.UUID, ...],
    db: DbSession,
    current_user: CurrentUserDep,
) -> User:
    await require_permission(db, current_user, "iam.users.read")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return user


@router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    db: DbSession,
    current_user: CurrentUserDep,
) -> User:
    await require_permission(db, current_user, "iam.users.write")
    user = User(**payload.model_dump())
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: Annotated[uuid.UUID, ...],
    payload: UserUpdate,
    db: DbSession,
    current_user: CurrentUserDep,
) -> User:
    await require_permission(db, current_user, "iam.users.write")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    user_id: Annotated[uuid.UUID, ...],
    db: DbSession,
    current_user: CurrentUserDep,
) -> None:
    await require_permission(db, current_user, "iam.users.write")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    user.is_active = False
    await db.commit()
