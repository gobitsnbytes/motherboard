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
    reviewer_id: uuid.UUID | None = None


class OnboardingReviewerAssign(BaseModel):
    reviewer_id: uuid.UUID


class OnboardingReviewerResponse(BaseModel):
    id: uuid.UUID
    display_name: str
    email: EmailStr | None = None
    avatar_url: str | None = None
    title: str | None = None
    discord_username: str


class OnboardingTeammateCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    date_of_birth: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    parent: OnboardingParentCreate | None = None


class OnboardingParticipantEmailUpdate(BaseModel):
    email: EmailStr


class OnboardingPortalSubmit(BaseModel):
    answers: dict[str, str | bool | int | None] = Field(default_factory=dict)
    document_answers: dict[str, dict[str, str | bool | int | None]] = Field(
        default_factory=dict
    )
    confirmed_identity: bool = False


class OnboardingDraftPatch(BaseModel):
    base_revision: int = Field(ge=0)
    values: dict[str, str | bool | int | dict | list | None] = Field(
        default_factory=dict
    )


class OnboardingDocumentSubmit(BaseModel):
    base_revision: int = Field(ge=0)
    confirmed_identity: bool = False


class OnboardingThreadCreate(BaseModel):
    field_id: str | None = Field(default=None, max_length=160)
    block_id: str | None = Field(default=None, max_length=160)
    quote: str | None = Field(default=None, max_length=1000)
    body: str = Field(min_length=1, max_length=4000)


class OnboardingThreadReply(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class OnboardingThreadStatusUpdate(BaseModel):
    status: str = Field(pattern=r"^(addressed|resolved|open)$")


class OnboardingChangesRequest(BaseModel):
    note: str | None = Field(default=None, max_length=4000)


class OnboardingHQFieldsPatch(BaseModel):
    base_revision: int = Field(ge=0)
    values: dict[str, str | bool | int | dict | list | None] = Field(
        default_factory=dict
    )


class OnboardingCompileRequest(BaseModel):
    base_revision: int = Field(ge=0)


class OnboardingSigningRollbackRequest(BaseModel):
    reason: str = Field(min_length=10, max_length=1000)


class OnboardingReviewCreate(BaseModel):
    decision: str = Field(pattern=r"^(accepted|changes_requested|rejected)$")
    document_id: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=2000)


class OnboardingCancelRequest(BaseModel):
    reason: str = Field(min_length=10, max_length=2000)


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
    revision_id: uuid.UUID | None = None
    current_revision: int = 0
    state_hash: str | None = None
    final_docx_hash: str | None = None
    final_pdf_hash: str | None = None


class OnboardingReviewCommentResponse(BaseModel):
    id: uuid.UUID
    author_kind: str
    author_ref: str
    body: str
    created_at: datetime


class OnboardingReviewThreadResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    field_id: str | None = None
    block_id: str | None = None
    quote: str | None = None
    status: str
    created_at: datetime
    comments: list[OnboardingReviewCommentResponse] = Field(default_factory=list)


class OnboardingEditorResponse(BaseModel):
    document: OnboardingDocumentResponse
    title: str
    fields: list[dict] = Field(default_factory=list)
    sections: list[dict] = Field(default_factory=list)
    values: dict = Field(default_factory=dict)
    threads: list[OnboardingReviewThreadResponse] = Field(default_factory=list)
    editable: bool
    can_submit: bool
    can_compile: bool = False
    can_approve: bool = False
    review_block_reason: str | None = None


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
    current_revision_id: uuid.UUID | None = None
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


class OnboardingInviteLink(BaseModel):
    role: str
    name: str
    email: EmailStr
    portal_url: str


class OnboardingTeammateInviteResponse(BaseModel):
    portal: OnboardingPortalResponse
    invitees: list[OnboardingInviteLink]
    email_sent: bool = False


class OnboardingDeleteResponse(BaseModel):
    ok: bool = True
    message: str
    id: str
    notified: list[str] = Field(default_factory=list)


class OnboardingRemindResponse(BaseModel):
    ok: bool = True
    reminded_count: int
    reminded: list[str] = Field(default_factory=list)
    email_sent: bool = False
