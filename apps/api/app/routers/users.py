"""Users router — CRUD for internal user records."""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.db.models import User
from app.dependencies import CurrentUserDep, DbSession
from app.iam.policy import require_permission
from app.schemas.users import UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/", response_model=list[UserOut])
async def list_users(db: DbSession, current_user: CurrentUserDep) -> list[User]:
    await require_permission(db, current_user, "iam.users.read")
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return list(result.scalars().all())


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
