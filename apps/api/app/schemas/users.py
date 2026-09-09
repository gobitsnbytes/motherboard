"""Pydantic v2 schemas for User endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserBase(BaseModel):
    display_name: str
    email: EmailStr | None = None
    avatar_url: str | None = None
    title: str | None = None
    bio: str | None = None
    timezone: str | None = None
    skills: list[str] | None = None
    chrono_v2_data: dict | None = None


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    display_name: str | None = None
    email: EmailStr | None = None
    avatar_url: str | None = None
    is_active: bool | None = None
    title: str | None = None
    bio: str | None = None
    timezone: str | None = None
    skills: list[str] | None = None
    chrono_v2_data: dict | None = None
    profile_completed: bool | None = None


class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_active: bool
    is_super_admin: bool
    profile_completed: bool = False
    created_at: datetime
    updated_at: datetime
