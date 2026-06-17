"""Pydantic v2 schemas for Fork and ForkMember endpoints."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ForkBase(BaseModel):
    slug: str
    city_name: str
    discord_city_role_id: str | None = None
    discord_contributor_role_id: str | None = None
    is_active: bool = True


class ForkCreate(ForkBase):
    metadata_json: dict[str, Any] = {}


class ForkUpdate(BaseModel):
    city_name: str | None = None
    discord_city_role_id: str | None = None
    discord_contributor_role_id: str | None = None
    is_active: bool | None = None
    metadata_json: dict[str, Any] | None = None


class ForkOut(ForkBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ForkMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    fork_id: uuid.UUID
    track: str | None
    local_role: str
    is_active: bool
    joined_at: datetime
    left_at: datetime | None
