"""Pydantic contracts for the public form builder."""
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator, model_validator


BlockType = Literal[
    "heading", "paragraph", "text", "textarea", "email", "phone", "number",
    "date", "url", "choice", "multichoice", "select", "file", "divider", "consent",
]


class FormBlock(BaseModel):
    id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    type: BlockType
    label: str = Field(default="", max_length=2_000)
    description: str | None = Field(default=None, max_length=2_000)
    required: bool = False
    options: list[str] | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def validate_block(self):
        answerable = self.type not in {"divider"}
        if answerable and not self.label.strip():
            raise ValueError("Every block except a divider needs text")
        if self.type in {"choice", "multichoice", "select"}:
            cleaned = [option.strip() for option in self.options or [] if option.strip()]
            if not cleaned:
                raise ValueError("Choice blocks need at least one option")
            if len(set(cleaned)) != len(cleaned):
                raise ValueError("Choice block options must be unique")
            self.options = cleaned
        else:
            self.options = None
        if self.type == "consent":
            self.required = True
        return self


class FormCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    slug: str = Field(min_length=3, max_length=160, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description_markdown: str | None = Field(default=None, max_length=20_000)
    blocks: list[FormBlock] = Field(default_factory=list, max_length=100)
    is_published: bool = False

    @field_validator("blocks")
    @classmethod
    def unique_block_ids(cls, blocks: list[FormBlock]) -> list[FormBlock]:
        ids = [block.id for block in blocks]
        if len(ids) != len(set(ids)):
            raise ValueError("Block IDs must be unique")
        return blocks


class FormUpdate(FormCreate):
    pass


class FormSubmissionCreate(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)
    accepted_terms: bool


class FormSubmissionReceipt(BaseModel):
    id: str
    status: str
    intake_status: str
    upload_token: str


class FormSubmissionResponse(BaseModel):
    id: str
    form_id: str
    created_at: datetime
    intake_status: str
    answers: dict[str, Any]
    labels: dict[str, str] = Field(default_factory=dict)
    uploads: list[dict[str, Any]] = Field(default_factory=list)
