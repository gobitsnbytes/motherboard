"""Fork-scoped access requires both a policy and a real fork assignment."""

from fastapi import HTTPException
from sqlalchemy import select

from app.db.models import Fork, ForkMember
from app.iam.access import active_grants
from app.iam.policy import can, require_permission


async def allowed_fork_ids(db, principal, permission):
    if await can(db, principal, permission):
        return None  # Global grant; callers may list every fork.
    scopes = {g.resource_scope for g in await active_grants(db, principal)
        if g.permission_key == permission and g.resource_scope}
    rows = (await db.execute(select(Fork.id, Fork.slug, ForkMember.local_role).join(ForkMember).where(
        ForkMember.user_id == principal.user_id, ForkMember.is_active.is_(True), Fork.is_active.is_(True),
    ))).all()
    return [id for id, slug, role in rows if f"fork:{slug}" in scopes
        and (not permission.endswith(".write") or role == "fork_lead")]


async def require_fork_access(db, principal, permission, fork_id):
    if await can(db, principal, permission):
        return
    allowed = await allowed_fork_ids(db, principal, permission)
    if fork_id not in allowed:
        raise HTTPException(403, "Missing permission or active assignment for this fork")
    fork = await db.get(Fork, fork_id)
    await require_permission(db, principal, permission, f"fork:{fork.slug}")


async def require_case_access(db, principal, permission, case):
    if case.fork_id:
        await require_fork_access(db, principal, permission, case.fork_id)
    else:
        await require_permission(db, principal, permission)
