"""Read and validate explicit IAM configuration; never create defaults."""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Fork, ForkMember, Grant, Group, Membership, Permission
from app.iam.principal import ResolvedPrincipal, resolve_principal
from app.iam.policy import require_permission
from app.schemas.iam import GrantResponse


async def active_grants(db: AsyncSession, principal: ResolvedPrincipal) -> list[Grant]:
    conditions = [and_(Grant.principal_type == "user", Grant.principal_id == principal.user_id)]
    if principal.group_ids:
        conditions.append(and_(Grant.principal_type == "group", Grant.principal_id.in_(principal.group_ids)))
    return list((await db.scalars(select(Grant).where(
        or_(*conditions),
        or_(Grant.expires_at.is_(None), Grant.expires_at > datetime.now(timezone.utc)),
    ).order_by(Grant.permission_key, Grant.id))).all())


async def describe_access(db: AsyncSession, user_id: uuid.UUID) -> dict:
    principal = await resolve_principal(db, user_id)
    grants = await active_grants(db, principal)
    groups = list((await db.scalars(select(Group).where(Group.id.in_(principal.group_ids)))).all())
    assignments = (await db.execute(select(ForkMember, Fork).join(Fork).where(
        ForkMember.user_id == user_id, ForkMember.is_active.is_(True), Fork.is_active.is_(True),
    ))).all()
    keys = set((await db.scalars(select(Permission.key))).all())
    global_keys = {g.permission_key for g in grants if g.resource_scope is None}
    return {
        "principal": principal.model_dump(),
        "grants": [GrantResponse.model_validate(g).model_dump() for g in grants],
        "groups": [{"id": g.id, "name": g.name, "slug": g.slug} for g in groups],
        "capabilities": sorted(keys if principal.is_super_admin else global_keys),
        "scoped_capabilities": [{"permission_key": g.permission_key, "resource_scope": g.resource_scope,
            "grant_id": g.id} for g in grants if g.resource_scope is not None],
        "fork_assignments": [{"fork_id": f.id, "slug": f.slug, "city_name": f.city_name,
            "local_role": m.local_role} for m, f in assignments],
    }


async def validate_scope(db: AsyncSession, scope: str | None) -> None:
    if scope is None:
        return
    if not scope.startswith("fork:") or not scope[5:] or len(scope) > 255:
        raise HTTPException(422, "Use an explicit fork:<slug> scope, or null for global access")
    if not await db.scalar(select(Fork.id).where(Fork.slug == scope[5:], Fork.is_active.is_(True))):
        raise HTTPException(404, "Active fork scope not found")


async def require_delegable(db: AsyncSession, actor: ResolvedPrincipal, key: str,
    scope: str | None, expires_at: datetime | None = None) -> None:
    """Delegation cannot widen the actor's scope or outlive their authority."""
    if actor.is_super_admin:
        return
    await require_permission(db, actor, key, scope)
    grants = [g for g in await active_grants(db, actor) if g.permission_key == key
        and (g.resource_scope is None or (scope is not None and g.resource_scope == scope))]
    def utc(value):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    memberships = (await db.scalars(select(Membership).where(
        Membership.user_id == actor.user_id, Membership.group_id.in_(actor.group_ids),
        or_(Membership.expires_at.is_(None), Membership.expires_at > datetime.now(timezone.utc)),
    ))).all()
    deadlines = []
    for grant in grants:
        limits = [utc(grant.expires_at)] if grant.expires_at else []
        if grant.principal_type == "group":
            membership = next((m for m in memberships if m.group_id == grant.principal_id), None)
            if membership is None:
                continue
            if membership.expires_at:
                limits.append(utc(membership.expires_at))
        if not limits:
            return
        deadlines.append(min(limits))
    if expires_at is None or not any(limit >= utc(expires_at) for limit in deadlines):
        raise HTTPException(403, "Delegation cannot outlive your permission")


async def require_group_delegable(db: AsyncSession, actor: ResolvedPrincipal, group_id: uuid.UUID,
    expires_at: datetime | None = None) -> None:
    grants = (await db.scalars(select(Grant).where(Grant.principal_type == "group",
        Grant.principal_id == group_id,
        or_(Grant.expires_at.is_(None), Grant.expires_at > datetime.now(timezone.utc)),
    ))).all()
    for grant in grants:
        limits = [value for value in (expires_at, grant.expires_at) if value is not None]
        deadline = min(value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value for value in limits) if limits else None
        await require_delegable(db, actor, grant.permission_key, grant.resource_scope,
            deadline)
