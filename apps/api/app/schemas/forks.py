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


class ComplianceCheckItem(BaseModel):
    key: str
    title: str
    passed: bool
    status: str  # "passed" | "failed" | "warning"
    details: str
    remedy: str | None = None


class ForkComplianceCheckOut(BaseModel):
    fork_id: uuid.UUID
    city_name: str
    slug: str
    health_score: int
    overall_status: str  # "compliant" | "warning" | "non_compliant"
    passed_checks_count: int
    total_checks_count: int
    checks: list[ComplianceCheckItem]
    assigned_track_leads: dict[str, str | None]
    created_at: datetime
    updated_at: datetime


class ForkOnboardingItem(BaseModel):
    fork_id: uuid.UUID
    city_name: str
    slug: str
    stage: str  # "submitted" | "in_review" | "compliance_check" | "approved" | "archived"
    is_active: bool
    health_score: int
    compliance_summary: ForkComplianceCheckOut
    track_leads_assigned_count: int
    member_count: int
    remedies_needed: list[str]


class OnboardingChecklistStepOut(BaseModel):
    key: str
    label: str
    completed: bool
    completed_at: datetime | None = None
    completed_by: str | None = None


class OnboardingStepUpdate(BaseModel):
    completed: bool


class ForkOnboardingDetailOut(BaseModel):
    fork_id: uuid.UUID
    city_name: str
    slug: str
    stage: str
    checklist: list[OnboardingChecklistStepOut]
    next_stage: str | None
    next_stage_blockers: list[str]
    health_score: int
    overall_status: str
    remedies: list[str]


class ForkStageActionPayload(BaseModel):
    action: str  # "advance" | "reject" | "archive" | "reactivate"
    reason: str | None = None


class ForkMemberCreate(BaseModel):
    user_id: uuid.UUID
    track: str | None = None  # tech | creative | ops | outreach
    local_role: str = "contributor"  # fork_lead | track_lead | contributor | community

