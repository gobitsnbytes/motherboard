"""Schemas for trusted auth bridge endpoints."""

import uuid

from pydantic import BaseModel, Field


class DiscordUpsertRequest(BaseModel):
    discord_id: str = Field(min_length=1, max_length=25)
    email: str | None = None
    username: str | None = Field(default=None, max_length=100)
    global_name: str | None = Field(default=None, max_length=100)
    avatar: str | None = Field(default=None, max_length=100)
    access_token: str | None = None


class DiscordUpsertResponse(BaseModel):
    user_id: uuid.UUID

