"""Pydantic v2 schemas for the bnb-signatures digital contract engine."""

from datetime import datetime
from typing import List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---------------------------------------------------------------------------
# Recipient Schemas
# ---------------------------------------------------------------------------

class RecipientCreate(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., max_length=255)
    email: EmailStr
    role: str = Field(default="signer")  # signer, viewer, cc
    signing_order: int = Field(default=1, ge=1)
    access_passcode: Optional[str] = Field(default=None, max_length=50)
    requires_otp: bool = Field(default=False)
    allowed_sig_type: Optional[str] = Field(default="any")  # "any", "dsc_only", "email_only"


class RecipientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    request_id: uuid.UUID
    name: str
    email: str
    role: str
    signing_order: int
    status: str
    access_token: str
    requires_otp: bool = False
    allowed_sig_type: Optional[str] = "any"
    dsc_type: Optional[str] = None
    dsc_issuer: Optional[str] = None
    dsc_serial: Optional[str] = None
    dsc_common_name: Optional[str] = None
    signed_at: Optional[datetime] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class OTPRequestPayload(BaseModel):
    email: EmailStr


class OTPVerifyRequest(BaseModel):
    otp: str = Field(..., min_length=6, max_length=6)


class DSCHardwareSealRequest(BaseModel):
    signature_hex: str
    certificate_pem: Optional[str] = None
    issuer: Optional[str] = None
    serial_number: Optional[str] = None
    common_name: Optional[str] = None
    fields: Optional[List["SignSubmissionFieldPayload"]] = []


# ---------------------------------------------------------------------------
# Field Schemas
# ---------------------------------------------------------------------------

class FieldCreate(BaseModel):
    recipient_id: str
    type: str = Field(..., description="signature, fullname, date, text, checkbox")
    page_number: int = Field(..., ge=1)
    pos_x: float = Field(..., ge=0, le=100)
    pos_y: float = Field(..., ge=0, le=100)
    width: float = Field(..., ge=0, le=100)
    height: float = Field(..., ge=0, le=100)
    required: bool = True
    value: Optional[str] = None


class FieldResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    request_id: uuid.UUID
    recipient_id: uuid.UUID
    type: str
    page_number: int
    pos_x: float
    pos_y: float
    width: float
    height: float
    required: bool
    value: Optional[str] = None


# ---------------------------------------------------------------------------
# Request Schemas
# ---------------------------------------------------------------------------

class SignatureRequestCreate(BaseModel):
    title: str = Field(..., max_length=255)
    file_path: str = Field(..., description="Path to uploaded document file")
    recipients: List[RecipientCreate]
    fields: List[FieldCreate]
    expires_in_days: Optional[int] = Field(default=30, ge=1, le=365)
    idempotency_key: Optional[str] = Field(default=None, max_length=100)


class SignatureRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    status: str
    original_file_path: str
    signed_file_path: Optional[str] = None
    document_hash: Optional[str] = None
    idempotency_key: Optional[str] = None
    created_by: Optional[uuid.UUID] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    recipients: List[RecipientResponse] = []
    fields: List[FieldResponse] = []


# ---------------------------------------------------------------------------
# Signing Portal & Audit Schemas
# ---------------------------------------------------------------------------

class SignSubmissionFieldPayload(BaseModel):
    field_id: uuid.UUID
    value: str  # Base64 image URL or text value


class SignSubmissionRequest(BaseModel):
    fields: List[SignSubmissionFieldPayload]
    passcode: Optional[str] = None


class SignatureAuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    request_id: uuid.UUID
    recipient_id: Optional[uuid.UUID] = None
    action: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    details: Optional[str] = None
    created_at: datetime


class DocumentVerificationResponse(BaseModel):
    document_id: uuid.UUID
    title: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    document_hash: Optional[str] = None
    total_signatories: int
    completed_signatories: int
    audit_trail: List[SignatureAuditLogResponse]
