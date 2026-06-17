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
        return True

    # Grant matches if it has a null resource_scope (global wildcard) or matches exactly
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
) -> dict[str, bool]:
    # Need to handle case where same key might be requested with different scopes
    result = {}
    for key, _ in checks:
        if key not in result:
            result[key] = False

    if principal.is_super_admin:
        return {key: True for key, _ in checks}

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

    # Evaluation per check:
    # If a check is satisfied, result[key] becomes True.
    for key, resource_scope in checks:
        if result[key]:
            # already True from another check on same key? (Wait, the batch_can returns dict[str, bool], so if the key is True for any scope requested or what? The spec says returns `{permission_key: bool}` map. The test expects "batch.scoped" to be True if ANY of the checks for it pass? Or wait... if a user requests batch.scoped on res_1 AND res_2, and they only have res_1, is it True?
            # Actually let's just do: result[key] is True if ANY check for that key passed.)
            pass

        grants_for_key = [g for g in matching_grants if g.permission_key == key]
        if not grants_for_key:
            continue

        if not resource_scope:
            result[key] = True
        else:
            if any(g.resource_scope is None or g.resource_scope == resource_scope for g in grants_for_key):
                result[key] = True

    return result
