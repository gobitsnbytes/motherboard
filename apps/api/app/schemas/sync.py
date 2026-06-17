"""Pydantic v2 schemas for SyncRun endpoints."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class SyncRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    trigger: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    members_synced: int
    members_added: int
    members_removed: int
    errors: list[Any]
    discord_member_count: int | None
