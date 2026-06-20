"""Groups router — manage internal permission groups and their memberships."""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.db.models import Group, Membership, User
from app.dependencies import CurrentUserDep, DbSession
from app.iam.policy import require_permission
from app.schemas.groups import GroupCreate, GroupOut, GroupUpdate, MembershipOut

router = APIRouter(prefix="/api/groups", tags=["groups"])


@router.get("/", response_model=list[GroupOut])
async def list_groups(db: DbSession, current_user: CurrentUserDep) -> list[Group]:
    await require_permission(db, current_user, "iam.groups.read")
    result = await db.execute(select(Group).order_by(Group.name))
    return list(result.scalars().all())


@router.get("/{group_id}", response_model=GroupOut)
async def get_group(
    group_id: Annotated[uuid.UUID, ...],
    db: DbSession,
    current_user: CurrentUserDep,
) -> Group:
    await require_permission(db, current_user, "iam.groups.read")
    group = await db.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found.")
    return group


@router.post("/", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
async def create_group(
    payload: GroupCreate,
    db: DbSession,
    current_user: CurrentUserDep,
) -> Group:
    await require_permission(db, current_user, "iam.groups.write")
    group = Group(**payload.model_dump())
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return group


@router.patch("/{group_id}", response_model=GroupOut)
async def update_group(
    group_id: Annotated[uuid.UUID, ...],
    payload: GroupUpdate,
    db: DbSession,
    current_user: CurrentUserDep,
) -> Group:
    await require_permission(db, current_user, "iam.groups.write")
    group = await db.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found.")
    if group.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System groups cannot be modified.",
        )
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(group, field, value)
    await db.commit()
    await db.refresh(group)
    return group


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: Annotated[uuid.UUID, ...],
    db: DbSession,
    current_user: CurrentUserDep,
) -> None:
    await require_permission(db, current_user, "iam.groups.write")
    group = await db.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found.")
    if group.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System groups cannot be deleted.",
        )
    await db.delete(group)
    await db.commit()


@router.get("/{group_id}/members", response_model=list[MembershipOut])
async def list_group_members(
    group_id: Annotated[uuid.UUID, ...],
    db: DbSession,
    current_user: CurrentUserDep,
) -> list[Membership]:
    await require_permission(db, current_user, "iam.groups.read")
    stmt = select(Membership).where(Membership.group_id == group_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/{group_id}/members/{user_id}", response_model=MembershipOut, status_code=status.HTTP_201_CREATED)
async def add_group_member(
    group_id: Annotated[uuid.UUID, ...],
    user_id: Annotated[uuid.UUID, ...],
    db: DbSession,
    current_user: CurrentUserDep,
) -> Membership:
    await require_permission(db, current_user, "iam.memberships.write")
    group = await db.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found.")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    membership = Membership(user_id=user_id, group_id=group_id, source="manual")
    db.add(membership)
    await db.commit()
    await db.refresh(membership)
    return membership


@router.delete("/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_group_member(
    group_id: Annotated[uuid.UUID, ...],
    user_id: Annotated[uuid.UUID, ...],
    db: DbSession,
    current_user: CurrentUserDep,
) -> None:
    await require_permission(db, current_user, "iam.memberships.write")
    stmt = select(Membership).where(
        Membership.group_id == group_id, Membership.user_id == user_id
    )
    result = await db.execute(stmt)
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found.")
    await db.delete(membership)
    await db.commit()
