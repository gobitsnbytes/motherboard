"""Audit log router — read-only access to the audit trail."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.db.models import AuditLog
from app.dependencies import DbSession
from app.schemas.audit import AuditLogOut

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/", response_model=list[AuditLogOut])
async def list_audit_log(
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    action: Annotated[str | None, Query()] = None,
    actor_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[AuditLog]:
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if actor_id:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())
