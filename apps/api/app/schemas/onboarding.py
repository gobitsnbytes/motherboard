"""Schemas for the portal-first digital onboarding workflow."""

from datetime import datetime
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class OnboardingParentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    email: EmailStr


class OnboardingParticipantCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    date_of_birth: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    is_volunteer: bool = True
    parent: OnboardingParentCreate | None = None


class OnboardingCaseCreate(BaseModel):
    kind: str = Field(pattern=r"^(volunteer|fork)$")
    title: str = Field(min_length=3, max_length=255)
    participant: OnboardingParticipantCreate
    fork_id: uuid.UUID | None = None
    fork_name: str | None = Field(default=None, max_length=100)


class OnboardingTeammateCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    date_of_birth: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    parent: OnboardingParentCreate | None = None


class OnboardingPortalSubmit(BaseModel):
    answers: dict[str, str | bool | int | None] = Field(default_factory=dict)
    confirmed_identity: bool = False


class OnboardingReviewCreate(BaseModel):
    decision: str = Field(pattern=r"^(accepted|changes_requested|rejected)$")
    document_id: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=2000)


class OnboardingCertificateCreate(BaseModel):
    director_one_name: str = Field(min_length=2, max_length=255)
    director_one_email: EmailStr
    director_two_name: str = Field(min_length=2, max_length=255)
    director_two_email: EmailStr


class OnboardingDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_key: str
    template_filename: str
    status: str
    signature_request_id: uuid.UUID | None = None
    signature_url: str | None = None
    evidence_hash: str | None = None
    canonical_hash: str | None = None
    completed_at: datetime | None = None


class OnboardingParticipantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    name: str
    email: str
    date_of_birth: str | None = None
    is_minor: bool
    status: str
    submitted_at: datetime | None = None
    documents: list[OnboardingDocumentResponse] = []
    portal_url: str | None = None


class OnboardingReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID | None = None
    reviewer_id: uuid.UUID
    decision: str
    note: str | None = None
    created_at: datetime


class OnboardingCaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    title: str
    status: str
    fork_id: uuid.UUID | None = None
    case_data: dict = {}
    created_by: uuid.UUID | None = None
    reviewer_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    participants: list[OnboardingParticipantResponse] = []
    documents: list[OnboardingDocumentResponse] = []
    reviews: list[OnboardingReviewResponse] = []


class OnboardingPortalResponse(BaseModel):
    case_id: uuid.UUID
    case_title: str
    case_kind: str
    participant: OnboardingParticipantResponse
    documents: list[OnboardingDocumentResponse]
    field_manifest: dict[str, list[dict]]
