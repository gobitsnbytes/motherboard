from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Grant
from .principal import ResolvedPrincipal

async def can(
    db: AsyncSession,
    principal: ResolvedPrincipal,
    permission_key: str,
    resource_scope: Optional[str] = None
) -> bool:
    if principal.is_super_admin:
        return True

    now = datetime.now(timezone.utc)

    # User-direct or group-level grants conditions
    principal_conditions = [
        and_(Grant.principal_type == "user", Grant.principal_id == principal.user_id)
    ]
    if principal.group_ids:
        principal_conditions.append(
            and_(Grant.principal_type == "group", Grant.principal_id.in_(principal.group_ids))
        )

    grant_filter = and_(
        or_(*principal_conditions),
        Grant.permission_key == permission_key,
        or_(Grant.expires_at.is_(None), Grant.expires_at > now)
    )

    stmt = select(Grant).where(grant_filter)
    res = await db.execute(stmt)
    matching_grants = res.scalars().all()

    if not matching_grants:
        return False

    if not resource_scope:
        return any(g.resource_scope is None for g in matching_grants)

    # A scoped check must never be satisfied by a grant scoped to another
    # resource. A null scope is the explicit global wildcard.
    return any(g.resource_scope is None or g.resource_scope == resource_scope for g in matching_grants)


async def require_permission(
    db: AsyncSession,
    principal: ResolvedPrincipal,
    permission_key: str,
    resource_scope: Optional[str] = None
) -> None:
    has_permission = await can(db, principal, permission_key, resource_scope)
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing permission: {permission_key}" + (f" on {resource_scope}" if resource_scope else "")
        )

async def batch_can(
    db: AsyncSession,
    principal: ResolvedPrincipal,
    checks: list[tuple[str, Optional[str]]]
) -> dict[tuple[str, Optional[str]], bool]:
    """Evaluate each permission/resource pair independently."""
    result = {check: False for check in dict.fromkeys(checks)}

    if principal.is_super_admin:
        return {check: True for check in result}

    if not checks:
        return result

    now = datetime.now(timezone.utc)

    # User-direct or group-level grants conditions
    principal_conditions = [
        and_(Grant.principal_type == "user", Grant.principal_id == principal.user_id)
    ]
    if principal.group_ids:
        principal_conditions.append(
            and_(Grant.principal_type == "group", Grant.principal_id.in_(principal.group_ids))
        )

    keys_to_check = [key for key, _ in checks]

    grant_filter = and_(
        or_(*principal_conditions),
        Grant.permission_key.in_(keys_to_check),
        or_(Grant.expires_at.is_(None), Grant.expires_at > now)
    )

    stmt = select(Grant).where(grant_filter)
    res = await db.execute(stmt)
    matching_grants = res.scalars().all()

    for key, resource_scope in checks:
        grants_for_key = [g for g in matching_grants if g.permission_key == key]
        if not grants_for_key:
            continue

        if not resource_scope or any(
            g.resource_scope is None or g.resource_scope == resource_scope
            for g in grants_for_key
        ):
            result[(key, resource_scope)] = True

    return result
