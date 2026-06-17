"""Forks router — city fork management and member listing."""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.db.models import Fork, ForkMember
from app.dependencies import DbSession
from app.schemas.forks import ForkCreate, ForkMemberOut, ForkOut, ForkUpdate

router = APIRouter(prefix="/api/forks", tags=["forks"])


@router.get("/", response_model=list[ForkOut])
async def list_forks(db: DbSession) -> list[Fork]:
    result = await db.execute(select(Fork).order_by(Fork.city_name))
    return list(result.scalars().all())


@router.get("/{fork_id}", response_model=ForkOut)
async def get_fork(fork_id: Annotated[uuid.UUID, ...], db: DbSession) -> Fork:
    fork = await db.get(Fork, fork_id)
    if not fork:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fork not found.")
    return fork


@router.post("/", response_model=ForkOut, status_code=status.HTTP_201_CREATED)
async def create_fork(payload: ForkCreate, db: DbSession) -> Fork:
    fork = Fork(**payload.model_dump())
    db.add(fork)
    await db.commit()
    await db.refresh(fork)
    return fork


@router.patch("/{fork_id}", response_model=ForkOut)
async def update_fork(
    fork_id: Annotated[uuid.UUID, ...],
    payload: ForkUpdate,
    db: DbSession,
) -> Fork:
    fork = await db.get(Fork, fork_id)
    if not fork:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fork not found.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(fork, field, value)
    await db.commit()
    await db.refresh(fork)
    return fork


@router.get("/{fork_id}/members", response_model=list[ForkMemberOut])
async def list_fork_members(fork_id: Annotated[uuid.UUID, ...], db: DbSession) -> list[ForkMember]:
    result = await db.execute(
        select(ForkMember).where(ForkMember.fork_id == fork_id, ForkMember.is_active.is_(True))
    )
    return list(result.scalars().all())
