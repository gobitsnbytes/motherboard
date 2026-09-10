"""Pydantic contracts for the public form builder."""
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class FormCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    slug: str = Field(min_length=3, max_length=160, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description_markdown: str | None = Field(default=None, max_length=20_000)
    blocks: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    is_published: bool = False


class FormUpdate(FormCreate):
    pass


class FormSubmissionCreate(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=16, max_length=100)
    accepted_terms: bool


class FormSubmissionResponse(BaseModel):
    id: str
    form_id: str
    created_at: datetime
    answers: dict[str, Any]
    labels: dict[str, str] = Field(default_factory=dict)
    uploads: list[dict[str, Any]] = Field(default_factory=list)
