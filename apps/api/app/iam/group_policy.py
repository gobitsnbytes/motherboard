"""Explicit, optimistic-concurrency-safe group policy changes."""

import hashlib
import json
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select

from app.db.models import Grant, Group, Permission
from app.iam.access import require_delegable, validate_scope
from app.iam.audit import write_audit_entry
from app.schemas.iam import GrantResponse


def policy_view(grants):
    rows = [GrantResponse.model_validate(g).model_dump(mode="json") for g in grants]
    rows.sort(key=lambda row: row["id"])
    return {"revision": hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest(), "grants": rows}


async def read_policy(db, group_id):
    if not await db.get(Group, group_id):
        raise HTTPException(404, "Group not found")
    return policy_view((await db.scalars(select(Grant).where(
        Grant.principal_type == "group", Grant.principal_id == group_id,
    ))).all())


async def replace_policy(db, actor, group_id, payload):
    group = await db.scalar(select(Group).where(Group.id == group_id).with_for_update())
    if group is None:
        raise HTTPException(404, "Group not found")
    old = list((await db.scalars(select(Grant).where(
        Grant.principal_type == "group", Grant.principal_id == group_id,
    ))).all())
    before = policy_view(old)
    if before["revision"] != payload.expected_revision:
        raise HTTPException(409, "Policy changed; reload before saving")
    seen = set()
    permissions = set((await db.scalars(select(Permission.key))).all())
    for entry in payload.grants:
        if entry.permission_key not in permissions:
            raise HTTPException(404, "Permission not found")
        pair = (entry.permission_key, entry.resource_scope)
        if pair in seen:
            raise HTTPException(422, "Duplicate permission and scope")
        seen.add(pair)
        await validate_scope(db, entry.resource_scope)
        if entry.expires_at and entry.expires_at <= datetime.now(timezone.utc):
            raise HTTPException(422, "Grant expiry must be in the future")
        await require_delegable(db, actor, entry.permission_key, entry.resource_scope, entry.expires_at)
    for grant in old:
        # The editor also needs authority over permissions they remove.
        if grant.expires_at is None or grant.expires_at.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
            await require_delegable(db, actor, grant.permission_key, grant.resource_scope, grant.expires_at)
        await db.delete(grant)
    new = [Grant(id=uuid.uuid4(), principal_type="group", principal_id=group_id,
        permission_key=entry.permission_key, resource_scope=entry.resource_scope,
        expires_at=entry.expires_at, granted_by=actor.user_id) for entry in payload.grants]
    db.add_all(new)
    await db.flush()
    after = policy_view(new)
    await write_audit_entry(db=db, actor_id=actor.user_id, action="iam.group_policy.updated",
        target_type="group", target_id=str(group_id), metadata={"before": before, "after": after})
    await db.commit()
    return after
