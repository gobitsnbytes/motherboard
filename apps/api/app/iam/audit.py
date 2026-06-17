import uuid
from typing import Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import AuditLog

async def write_audit_entry(
    db: AsyncSession,
    actor_id: Optional[uuid.UUID],
    action: str,
    target_type: str,
    target_id: str,
    metadata: dict[str, Any]
) -> AuditLog:
    """
    Inserts an AuditLog row but does NOT commit. The caller owns the transaction.
    """
    audit_entry = AuditLog(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata_json=metadata
    )
    db.add(audit_entry)
    return audit_entry
