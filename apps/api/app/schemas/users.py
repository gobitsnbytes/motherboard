"""Pydantic v2 schemas for User endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserBase(BaseModel):
    display_name: str
    email: EmailStr | None = None
    avatar_url: str | None = None


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    display_name: str | None = None
    email: EmailStr | None = None
    avatar_url: str | None = None
    is_active: bool | None = None


class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_active: bool
    is_super_admin: bool
    created_at: datetime
    updated_at: datetime
