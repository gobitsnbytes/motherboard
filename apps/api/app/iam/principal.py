import uuid
from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.db.models import User, Membership

class ResolvedPrincipal(BaseModel):
    user_id: uuid.UUID
    group_ids: List[uuid.UUID]
    is_super_admin: bool

async def resolve_principal(db: AsyncSession, user_id: uuid.UUID) -> ResolvedPrincipal:
    user_stmt = select(User).where(User.id == user_id)
    user_res = await db.execute(user_stmt)
    user = user_res.scalar_one_or_none()

    if not user or not user.is_active:
        raise ValueError("User not found or deactivated")

    membership_stmt = select(Membership.group_id).where(Membership.user_id == user_id)
    membership_res = await db.execute(membership_stmt)
    group_ids = list(membership_res.scalars().all())

    return ResolvedPrincipal(
        user_id=user.id,
        group_ids=group_ids,
        is_super_admin=user.is_super_admin
    )
