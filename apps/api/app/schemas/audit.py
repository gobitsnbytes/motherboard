"""Pydantic v2 schemas for AuditLog endpoints."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_id: uuid.UUID | None
    action: str
    target_type: str
    target_id: str
    metadata_json: dict[str, Any]
    ip_address: str | None
    plugin_id: str | None
    created_at: datetime
