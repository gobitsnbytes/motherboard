"""Pydantic v2 schemas for Group and Membership endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class GroupBase(BaseModel):
    slug: str
    name: str
    description: str | None = None
    color_hex: str | None = None


class GroupCreate(GroupBase):
    pass


class GroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    color_hex: str | None = None


class GroupOut(GroupBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_system: bool
    created_at: datetime
    updated_at: datetime


class MembershipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    group_id: uuid.UUID
    source: str
    granted_by: uuid.UUID | None
    granted_at: datetime
    expires_at: datetime | None
