"""Pydantic v2 schemas for the Dyslexic sponsorship outreach module."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.dyslexic.constants import (
    COMPANY_STAGES,
    CONTACT_STATUSES,
    OUTREACH_KINDS,
    OUTREACH_OUTCOMES,
)

StageLiteral = Literal[COMPANY_STAGES]  # type: ignore[valid-type]
OutcomeLiteral = Literal[OUTREACH_OUTCOMES]  # type: ignore[valid-type]
KindLiteral = Literal[OUTREACH_KINDS]  # type: ignore[valid-type]
ContactStatusLiteral = Literal[CONTACT_STATUSES]  # type: ignore[valid-type]


class ActorOut(BaseModel):
    """A volunteer, as shown next to something they did."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str
    avatar_url: str | None = None


# ---------------------------------------------------------------------------
# Companies
# ---------------------------------------------------------------------------

class CompanyCreate(BaseModel):
    """Two fields is the whole ask — research fills in the rest."""

    name: str = Field(..., min_length=1, max_length=200)
    website: str | None = Field(None, max_length=500)
    fork_id: uuid.UUID | None = None
    notes: str | None = None


class CompanyUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    website: str | None = Field(None, max_length=500)
    notes: str | None = None
    stage: StageLiteral | None = None
    fork_id: uuid.UUID | None = None
    is_archived: bool | None = None


class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    website: str | None
    normalized_domain: str | None
    stage: str
    research_status: str
    research_json: dict[str, Any]
    research_error: str | None
    research_generated_at: datetime | None
    research_model: str | None
    notes: str | None
    added_by: uuid.UUID | None
    fork_id: uuid.UUID | None
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    contact_count: int = 0
    added_by_name: str | None = None


class CompanyDetailOut(CompanyOut):
    """Company page payload — everything the detail view renders in one call."""

    contacts: list["ContactOut"] = []
    timeline: list["EventOut"] = []


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------

class ContactCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    role: str | None = Field(None, max_length=150)
    email: str | None = Field(None, max_length=255)
    linkedin_url: str | None = Field(None, max_length=500)
    notes: str | None = None


class ContactUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=150)
    role: str | None = Field(None, max_length=150)
    email: str | None = Field(None, max_length=255)
    linkedin_url: str | None = Field(None, max_length=500)
    notes: str | None = None
    status: ContactStatusLiteral | None = None
    is_archived: bool | None = None


class ContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    role: str | None
    email: str | None
    linkedin_url: str | None
    notes: str | None
    status: str
    contacted_by: uuid.UUID | None
    contacted_at: datetime | None
    claimed_by: uuid.UUID | None
    claim_expires_at: datetime | None
    added_by: uuid.UUID | None
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    # Resolved names so the table does not need a second round-trip per row.
    contacted_by_name: str | None = None
    claimed_by_name: str | None = None
    company_name: str | None = None


class ContactCreateOut(ContactOut):
    """
    Adding a contact who already exists at another company is allowed — people
    change jobs — but the volunteer is told, so it is a decision rather than an
    accident.
    """

    duplicate_warning: str | None = None


# ---------------------------------------------------------------------------
# Emails, outreach, follow-ups
# ---------------------------------------------------------------------------

class EmailGenerateIn(BaseModel):
    kind: KindLiteral = "initial"
    tone: str | None = Field(None, max_length=30)
    extra_context: str | None = None


class EmailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contact_id: uuid.UUID
    company_id: uuid.UUID
    kind: str
    subject: str
    body: str
    tone: str | None
    model: str | None
    generated_by: uuid.UUID | None
    created_at: datetime


class SendIn(BaseModel):
    """The 'I've Sent Email' click. `email_id` is null when written by hand."""

    email_id: uuid.UUID | None = None
    kind: KindLiteral = "initial"


class OutcomeIn(BaseModel):
    outcome: OutcomeLiteral
    note: str | None = None


class OutreachOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contact_id: uuid.UUID
    company_id: uuid.UUID
    email_id: uuid.UUID | None
    kind: str
    sent_by: uuid.UUID | None
    sent_at: datetime
    outcome: str | None
    outcome_at: datetime | None
    outcome_by: uuid.UUID | None
    outcome_note: str | None
    sent_by_name: str | None = None


class FollowUpResolveIn(BaseModel):
    note: str | None = None


class FollowUpOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    outreach_id: uuid.UUID
    contact_id: uuid.UUID
    company_id: uuid.UUID
    assigned_to: uuid.UUID | None
    due_at: datetime
    status: str
    resolved_at: datetime | None
    created_at: datetime
    contact_name: str | None = None
    company_name: str | None = None
    assigned_to_name: str | None = None
    is_overdue: bool = False


# ---------------------------------------------------------------------------
# Timeline, stats, leaderboard
# ---------------------------------------------------------------------------

class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    contact_id: uuid.UUID | None
    actor_id: uuid.UUID | None
    kind: str
    summary: str
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    actor_name: str | None = None
    actor_avatar: str | None = None
    company_name: str | None = None


class StatsOut(BaseModel):
    companies: int
    contacts: int
    emails_sent: int
    replies: int
    follow_ups_due: int
    my_follow_ups_due: int
    sponsors_closed: int


class LeaderboardRowOut(BaseModel):
    user_id: uuid.UUID
    display_name: str
    avatar_url: str | None = None
    companies_added: int = 0
    contacts_added: int = 0
    emails_sent: int = 0
    follow_ups_sent: int = 0
    replies_received: int = 0
    meetings_scheduled: int = 0
    sponsors_closed: int = 0
    score: int = 0


CompanyDetailOut.model_rebuild()
