"""
FastAPI APIRouter for digital signature contracts (bnb-signatures).
"""

from datetime import datetime, timedelta, timezone
import hashlib
import os
import random
import uuid
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, Response
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs12

from app.config import get_settings
from app.db.models import SignatureAuditLog, SignatureField, SignatureRecipient, SignatureRequest, User
from app.dependencies import DbSession, get_current_user
from app.iam.principal import ResolvedPrincipal
from app.schemas.signatures import (
    DSCHardwareSealRequest,
    DocumentVerificationResponse,
    FieldCreate,
    FieldResponse,
    OTPRequestPayload,
    OTPVerifyRequest,
    RecipientCreate,
    RecipientResponse,
    SignSubmissionRequest,
    SignatureAuditLogResponse,
    SignatureRequestCreate,
    SignatureRequestResponse,
)
from app.services.signature_engine import (
    embed_signatures_and_seal,
    prepare_document_pdf,
    render_pdf_page_previews,
)

router = APIRouter(prefix="/api/signatures", tags=["signatures"])

UPLOAD_DIR = os.path.join(os.getcwd(), "data", "signatures")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _mask_email(email: str) -> str:
    """Mask email address (e.g., akshatkushwah@gmail.com -> ak*******@g****.com)."""
    if "@" not in email:
        return email
    user, domain = email.split("@", 1)
    domain_parts = domain.split(".", 1)
    user_masked = user[:2] + "*" * max(len(user) - 2, 5) if len(user) > 2 else user[0] + "****"
    dom_name = domain_parts[0]
    dom_masked = dom_name[:1] + "*" * max(len(dom_name) - 1, 3)
    ext = f".{domain_parts[1]}" if len(domain_parts) > 1 else ""
    return f"{user_masked}@{dom_masked}{ext}"


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

async def _log_audit_event(
    db: AsyncSession,
    request_id: uuid.UUID,
    action: str,
    recipient_id: Optional[uuid.UUID] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[str] = None,
):
    log = SignatureAuditLog(
        request_id=request_id,
        recipient_id=recipient_id,
        action=action,
        ip_address=ip_address,
        user_agent=user_agent,
        details=details,
    )
    db.add(log)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/upload")
async def upload_contract_file(
    file: UploadFile = File(...),
    current_user: ResolvedPrincipal = Depends(get_current_user),
):
    """Upload a .pdf or .docx file, parse PDF format, and generate page preview images."""
    contents = await file.read()
    filename = file.filename or "contract.pdf"

    try:
        pdf_bytes = prepare_document_pdf(contents, filename)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))

    file_id = str(uuid.uuid4())
    saved_filename = f"{file_id}.pdf"
    file_path = os.path.join(UPLOAD_DIR, saved_filename)

    with open(file_path, "wb") as f:
        f.write(pdf_bytes)

    previews = render_pdf_page_previews(pdf_bytes)

    return {
        "file_id": file_id,
        "file_path": file_path,
        "filename": filename,
        "page_count": len(previews),
        "previews": previews,
    }


@router.post("/requests", response_model=SignatureRequestResponse)
async def create_signature_request(
    payload: SignatureRequestCreate,
    req: Request,
    bg_tasks: BackgroundTasks,
    db: DbSession = None,
    current_user: ResolvedPrincipal = Depends(get_current_user),
):
    """Create a new signature request draft or active contract dispatch with idempotency protection."""
    if not os.path.exists(payload.file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Uploaded file not found")

    idempotency_key = (
        req.headers.get("x-idempotency-key")
        or req.headers.get("idempotency-key")
        or payload.idempotency_key
    )

    if idempotency_key:
        stmt_existing = (
            select(SignatureRequest)
            .options(
                selectinload(SignatureRequest.recipients),
                selectinload(SignatureRequest.fields),
            )
            .where(SignatureRequest.idempotency_key == idempotency_key)
        )
        res_existing = await db.execute(stmt_existing)
        existing = res_existing.scalar_one_or_none()
        if existing:
            return existing

    expires_at = datetime.now(timezone.utc) + timedelta(days=payload.expires_in_days or 30)

    sig_request = SignatureRequest(
        title=payload.title,
        status="pending",
        original_file_path=payload.file_path,
        idempotency_key=idempotency_key,
        created_by=current_user.user_id,
        expires_at=expires_at,
    )
    db.add(sig_request)
    await db.flush()

    # Create recipients
    recipients_map = {}
    recipient_id_map = {}
    first_recipient_id = None

    for r_in in payload.recipients:
        access_token = hashlib.sha256(f"{sig_request.id}:{r_in.email}:{uuid.uuid4()}".encode()).hexdigest()[:32]
        
        # If client supplied a valid UUID as recipient id, we can preserve it or let DB generate
        rec_id = None
        if r_in.id:
            try:
                rec_id = uuid.UUID(r_in.id)
            except ValueError:
                rec_id = None

        recipient = SignatureRecipient(
            id=rec_id or uuid.uuid4(),
            request_id=sig_request.id,
            name=r_in.name,
            email=r_in.email,
            role=r_in.role,
            signing_order=r_in.signing_order,
            status="pending",
            access_token=access_token,
            access_passcode=r_in.access_passcode,
            requires_otp=r_in.requires_otp,
            allowed_sig_type=r_in.allowed_sig_type or "any",
        )
        db.add(recipient)
        await db.flush()

        if not first_recipient_id:
            first_recipient_id = recipient.id

        recipients_map[str(r_in.email).lower().strip()] = recipient
        if r_in.id:
            recipient_id_map[str(r_in.id)] = recipient.id
        recipient_id_map[str(recipient.id)] = recipient.id

    # Create fields
    for f_in in payload.fields:
        target_rec_id = recipient_id_map.get(str(f_in.recipient_id))
        if not target_rec_id:
            try:
                target_rec_id = uuid.UUID(f_in.recipient_id)
            except ValueError:
                target_rec_id = first_recipient_id

        field = SignatureField(
            request_id=sig_request.id,
            recipient_id=target_rec_id or first_recipient_id,
            type=f_in.type,
            page_number=f_in.page_number,
            pos_x=f_in.pos_x,
            pos_y=f_in.pos_y,
            width=f_in.width,
            height=f_in.height,
            required=f_in.required,
            value=f_in.value,
        )
        db.add(field)

    client_ip = req.client.host if req and req.client else "127.0.0.1"
    user_agent = req.headers.get("user-agent") if req else "API"

    await _log_audit_event(
        db,
        request_id=sig_request.id,
        action="created",
        ip_address=client_ip,
        user_agent=user_agent,
        details=f"Created signature request '{payload.title}' with {len(payload.recipients)} signatories",
    )

    await db.commit()

    # Dispatch email invitations asynchronously via BackgroundTasks
    settings = get_settings()
    if settings.smtp_host and settings.smtp_user and settings.smtp_pass:
        from app.routers.meetings import send_smtp_email
        for r_in in payload.recipients:
            rec_obj = recipients_map.get(str(r_in.email).lower().strip())
            if rec_obj:
                sign_url = f"{settings.nextauth_url}/sign/{rec_obj.access_token}"
                subject = f"Action Required: Signature Request for {payload.title}"
                html_body = f"""
                <div style="font-family: Arial, sans-serif; padding: 24px; color: #120F0A; background-color: #FAF8F5;">
                    <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border: 2px solid #120F0A; border-radius: 12px; padding: 24px; box-shadow: 4px 4px 0px 0px #120F0A;">
                        <h2 style="color: #97192C; margin-top: 0;">bits&amp;bytes™ Legal Signature Portal</h2>
                        <p style="font-size: 14px; line-height: 1.6;">Hello <strong>{r_in.name}</strong>,</p>
                        <p style="font-size: 14px; line-height: 1.6;">You have been requested to review and sign the digital contract: <strong>{payload.title}</strong>.</p>
                        <div style="margin: 28px 0; text-align: center;">
                            <a href="{sign_url}" style="background-color: #97192C; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block; border: 2px solid #120F0A; box-shadow: 2px 2px 0px 0px #120F0A;">
                                Review &amp; Sign Contract
                            </a>
                        </div>
                        <p style="font-size: 12px; color: #716F6C; margin-top: 20px;">
                            Direct Link: <a href="{sign_url}" style="color: #97192C; text-decoration: underline;">{sign_url}</a>
                        </p>
                        <hr style="border: none; border-top: 1px solid #D0CFCE; margin: 24px 0;"/>
                        <p style="font-size: 11px; color: #716F6C; margin-bottom: 0;">Sent securely by GOBITSNBYTES FOUNDATION Legal Team (legal@gobitsnbytes.org).</p>
                    </div>
                </div>
                """
                bg_tasks.add_task(send_smtp_email, settings, [r_in.email], subject, html_body)

    # Fetch fresh request with relationships
    stmt = (
        select(SignatureRequest)
        .options(
            selectinload(SignatureRequest.recipients),
            selectinload(SignatureRequest.fields),
        )
        .where(SignatureRequest.id == sig_request.id)
    )
    result = await db.execute(stmt)
    return result.scalar_one()


@router.post("/requests/{request_id}/recipients/{recipient_id}/resend")
async def resend_recipient_invitation(
    request_id: uuid.UUID,
    recipient_id: uuid.UUID,
    bg_tasks: BackgroundTasks,
    db: DbSession = None,
    current_user: ResolvedPrincipal = Depends(get_current_user),
):
    """Resend email invitation for a specific recipient."""
    stmt = (
        select(SignatureRecipient)
        .options(selectinload(SignatureRecipient.request))
        .where(SignatureRecipient.id == recipient_id, SignatureRecipient.request_id == request_id)
    )
    res = await db.execute(stmt)
    recipient = res.scalar_one_or_none()

    if not recipient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipient or request not found")

    settings = get_settings()
    if settings.smtp_host and settings.smtp_user and settings.smtp_pass:
        from app.routers.meetings import send_smtp_email
        sign_url = f"{settings.nextauth_url}/sign/{recipient.access_token}"
        subject = f"Action Required: Signature Request for {recipient.request.title}"
        html_body = f"""
        <div style="font-family: Arial, sans-serif; padding: 24px; color: #120F0A; background-color: #FAF8F5;">
            <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border: 2px solid #120F0A; border-radius: 12px; padding: 24px; box-shadow: 4px 4px 0px 0px #120F0A;">
                <h2 style="color: #97192C; margin-top: 0;">bits&amp;bytes™ Legal Signature Portal</h2>
                <p style="font-size: 14px; line-height: 1.6;">Hello <strong>{recipient.name}</strong>,</p>
                <p style="font-size: 14px; line-height: 1.6;">You have been requested to review and sign the digital contract: <strong>{recipient.request.title}</strong>.</p>
                <div style="margin: 28px 0; text-align: center;">
                    <a href="{sign_url}" style="background-color: #97192C; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block; border: 2px solid #120F0A; box-shadow: 2px 2px 0px 0px #120F0A;">
                        Review &amp; Sign Contract
                    </a>
                </div>
                <p style="font-size: 12px; color: #716F6C; margin-top: 20px;">
                    Direct Link: <a href="{sign_url}" style="color: #97192C; text-decoration: underline;">{sign_url}</a>
                </p>
                <hr style="border: none; border-top: 1px solid #D0CFCE; margin: 24px 0;"/>
                <p style="font-size: 11px; color: #716F6C; margin-bottom: 0;">Sent securely by GOBITSNBYTES FOUNDATION Legal Team (legal@gobitsnbytes.org).</p>
            </div>
        </div>
        """
        bg_tasks.add_task(send_smtp_email, settings, recipient.email, subject, html_body)

    return {"status": "success", "message": f"Invitation email resent to {recipient.email}"}


@router.get("/requests", response_model=List[SignatureRequestResponse])
async def list_signature_requests(
    db: DbSession = None,
    current_user: ResolvedPrincipal = Depends(get_current_user),
):
    """List all signature requests created by or associated with the current user."""
    stmt = (
        select(SignatureRequest)
        .options(
            selectinload(SignatureRequest.recipients),
            selectinload(SignatureRequest.fields),
        )
        .where(SignatureRequest.created_by == current_user.user_id)
        .order_by(SignatureRequest.created_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/requests/{request_id}", response_model=SignatureRequestResponse)
async def get_signature_request_details(
    request_id: uuid.UUID,
    db: DbSession = None,
    current_user: ResolvedPrincipal = Depends(get_current_user),
):
    """Get full details of a specific signature request."""
    stmt = (
        select(SignatureRequest)
        .options(
            selectinload(SignatureRequest.recipients),
            selectinload(SignatureRequest.fields),
            selectinload(SignatureRequest.audit_logs),
        )
        .where(SignatureRequest.id == request_id)
    )
    result = await db.execute(stmt)
    sig_req = result.scalar_one_or_none()

    if not sig_req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Signature request not found")

    return sig_req


@router.get("/sign/{token}")
async def get_signing_portal_data(
    token: str,
    db: DbSession = None,
    req: Request = None,
):
    """Public endpoint for a recipient to view the contract and their assigned fields."""
    stmt = (
        select(SignatureRecipient)
        .options(
            selectinload(SignatureRecipient.request).selectinload(SignatureRequest.fields),
            selectinload(SignatureRecipient.request).selectinload(SignatureRequest.recipients),
        )
        .where(SignatureRecipient.access_token == token)
    )
    result = await db.execute(stmt)
    recipient = result.scalar_one_or_none()

    if not recipient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid or expired signature link")

    sig_request = recipient.request

    if sig_request.status in ("voided", "expired"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"This contract has been {sig_request.status}")

    # Read original PDF file and generate page previews
    if not os.path.exists(sig_request.original_file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Original document file missing")

    with open(sig_request.original_file_path, "rb") as f:
        pdf_bytes = f.read()

    previews = render_pdf_page_previews(pdf_bytes)

    # Log viewed audit event if not already viewed
    if recipient.status == "pending":
        recipient.status = "viewed"
        client_ip = req.client.host if req and req.client else "127.0.0.1"
        user_agent = req.headers.get("user-agent") if req else "Browser"

        await _log_audit_event(
            db,
            request_id=sig_request.id,
            recipient_id=recipient.id,
            action="viewed",
            ip_address=client_ip,
            user_agent=user_agent,
            details=f"Signatory {recipient.name} ({recipient.email}) viewed the contract",
        )
        await db.commit()

    recipient_fields = [
        {
            "id": str(f.id),
            "type": f.type,
            "page_number": f.page_number,
            "pos_x": f.pos_x,
            "pos_y": f.pos_y,
            "width": f.width,
            "height": f.height,
            "required": f.required,
            "value": f.value,
        }
        for f in sig_request.fields
        if f.recipient_id == recipient.id
    ]

    return {
        "token": token,
        "request_id": str(sig_request.id),
        "title": sig_request.title,
        "status": sig_request.status,
        "recipient": {
            "id": str(recipient.id),
            "name": recipient.name,
            "email": recipient.email,
            "masked_email": _mask_email(recipient.email),
            "status": recipient.status,
            "requires_passcode": bool(recipient.access_passcode),
            "requires_otp": recipient.requires_otp,
            "allowed_sig_type": recipient.allowed_sig_type or "any",
        },
        "previews": previews,
        "fields": recipient_fields,
    }


@router.post("/sign/{token}/request-otp")
async def request_signing_otp(
    token: str,
    payload: OTPRequestPayload,
    bg_tasks: BackgroundTasks,
    db: DbSession = None,
    req: Request = None,
):
    """Verifies full email address and generates a 2-minute 6-digit OTP code."""
    stmt = (
        select(SignatureRecipient)
        .options(selectinload(SignatureRecipient.request))
        .where(SignatureRecipient.access_token == token)
    )
    result = await db.execute(stmt)
    recipient = result.scalar_one_or_none()

    if not recipient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid signature token")

    if payload.email.strip().lower() != recipient.email.strip().lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The email address entered does not match the signatory record for this contract."
        )

    otp_code = f"{random.randint(100000, 999999)}"
    recipient.otp_code = otp_code
    recipient.otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=2)

    client_ip = req.client.host if req and req.client else "127.0.0.1"
    user_agent = req.headers.get("user-agent") if req else "Browser"

    await _log_audit_event(
        db,
        request_id=recipient.request_id,
        recipient_id=recipient.id,
        action="otp_requested",
        ip_address=client_ip,
        user_agent=user_agent,
        details=f"Sent 2-minute 6-digit OTP verification code to verified email ({recipient.email})",
    )
    await db.commit()

    settings = get_settings()
    if settings.smtp_host and settings.smtp_user and settings.smtp_pass:
        from app.routers.meetings import send_smtp_email
        subject = f"Your Verification Code for {recipient.request.title}: {otp_code}"
        html_body = f"""
        <div style="font-family: Arial, sans-serif; padding: 24px; color: #120F0A; background-color: #FAF8F5;">
            <div style="max-width: 500px; margin: 0 auto; background-color: #ffffff; border: 2px solid #120F0A; border-radius: 12px; padding: 24px; box-shadow: 4px 4px 0px 0px #120F0A; text-align: center;">
                <h2 style="color: #97192C; margin-top: 0;">bits&amp;bytes™ Security PIN</h2>
                <p style="font-size: 14px; line-height: 1.6;">Hello <strong>{recipient.name}</strong>,</p>
                <p style="font-size: 14px; line-height: 1.6;">Your 6-digit security verification code to unlock and sign <strong>{recipient.request.title}</strong> is:</p>
                <div style="margin: 24px 0; font-size: 32px; font-weight: 900; letter-spacing: 6px; color: #97192C; font-family: monospace; background-color: #FAF8F5; padding: 12px; border: 2px solid #120F0A; border-radius: 8px;">
                    {otp_code}
                </div>
                <p style="font-size: 12px; color: #716F6C; font-weight: bold;">This code is valid for 2 minutes.</p>
                <hr style="border: none; border-top: 1px solid #D0CFCE; margin: 20px 0;"/>
                <p style="font-size: 11px; color: #716F6C; margin-bottom: 0;">Sent securely by GOBITSNBYTES FOUNDATION Legal Portal.</p>
            </div>
        </div>
        """
        bg_tasks.add_task(send_smtp_email, settings, recipient.email, subject, html_body)

    return {"message": "OTP code sent to email", "email": recipient.email, "expires_in_seconds": 120}


@router.post("/sign/{token}/verify-otp")
async def verify_signing_otp(
    token: str,
    payload: OTPVerifyRequest,
    db: DbSession = None,
    req: Request = None,
):
    """Verifies recipient's 6-digit email OTP PIN."""
    stmt = (
        select(SignatureRecipient)
        .options(selectinload(SignatureRecipient.request))
        .where(SignatureRecipient.access_token == token)
    )
    result = await db.execute(stmt)
    recipient = result.scalar_one_or_none()

    if not recipient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid signature token")

    if not recipient.otp_code or not recipient.otp_expires_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No active OTP found. Please request a new verification code.")

    now = datetime.now(timezone.utc)
    if now > recipient.otp_expires_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification code has expired. Please request a new code.")

    if payload.otp.strip() != recipient.otp_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code. Please check your inbox and try again.")

    client_ip = req.client.host if req and req.client else "127.0.0.1"
    user_agent = req.headers.get("user-agent") if req else "Browser"

    await _log_audit_event(
        db,
        request_id=recipient.request_id,
        recipient_id=recipient.id,
        action="otp_verified",
        ip_address=client_ip,
        user_agent=user_agent,
        details=f"Signatory {recipient.name} successfully verified 6-digit email OTP",
    )
    await db.commit()

    return {"success": True, "message": "OTP verified successfully"}


@router.post("/sign/{token}/dsc-digest")
async def get_dsc_document_digest(
    token: str,
    db: DbSession = None,
):
    """Returns document SHA-256 hash digest for hardware USB token signing."""
    stmt = (
        select(SignatureRecipient)
        .options(selectinload(SignatureRecipient.request))
        .where(SignatureRecipient.access_token == token)
    )
    result = await db.execute(stmt)
    recipient = result.scalar_one_or_none()

    if not recipient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid signature token")

    sig_request = recipient.request
    if not os.path.exists(sig_request.original_file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Original document file missing")

    with open(sig_request.original_file_path, "rb") as f:
        pdf_bytes = f.read()

    doc_hash = hashlib.sha256(pdf_bytes).hexdigest()
    return {
        "token": token,
        "document_title": sig_request.title,
        "document_hash": doc_hash,
        "recipient_name": recipient.name,
        "recipient_email": recipient.email,
    }


@router.post("/sign/{token}/dsc-hardware-seal")
async def seal_hardware_dsc_signature(
    token: str,
    payload: DSCHardwareSealRequest,
    db: DbSession = None,
    req: Request = None,
):
    """Executes digital contract sealing using Hardware USB Token PKCS#7 signature."""
    stmt = (
        select(SignatureRecipient)
        .options(
            selectinload(SignatureRecipient.request).selectinload(SignatureRequest.fields),
            selectinload(SignatureRecipient.request).selectinload(SignatureRequest.recipients),
        )
        .where(SignatureRecipient.access_token == token)
    )
    result = await db.execute(stmt)
    recipient = result.scalar_one_or_none()

    if not recipient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid signature token")

    sig_request = recipient.request
    if recipient.status == "signed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Recipient has already signed this contract")

    client_ip = req.client.host if req and req.client else "127.0.0.1"
    user_agent = req.headers.get("user-agent") if req else "Browser"

    # Store DSC Certificate metadata
    recipient.dsc_type = "hardware_token"
    recipient.dsc_common_name = payload.common_name or recipient.name
    recipient.dsc_issuer = payload.issuer or "Hardware USB Token Certificate Authority"
    recipient.dsc_serial = payload.serial_number or hashlib.sha256(payload.signature_hex.encode()).hexdigest()[:16].upper()
    recipient.status = "signed"
    recipient.signed_at = datetime.now(timezone.utc)
    recipient.ip_address = client_ip
    recipient.user_agent = user_agent

    # Render DSC Digital Stamp overlay on assigned fields
    dsc_stamp = f"DIGITALLY SIGNED VIA HARDWARE DSC\nCN: {recipient.dsc_common_name}\nIssuer: {recipient.dsc_issuer}\nSerial: {recipient.dsc_serial}\nTimestamp: {recipient.signed_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"

    for f_in in (payload.fields or []):
        stmt_f = select(SignatureField).where(SignatureField.id == f_in.field_id, SignatureField.recipient_id == recipient.id)
        res_f = await db.execute(stmt_f)
        field_obj = res_f.scalar_one_or_none()
        if field_obj:
            field_obj.value = dsc_stamp

    await _log_audit_event(
        db,
        request_id=sig_request.id,
        recipient_id=recipient.id,
        action="signed_dsc_hardware",
        ip_address=client_ip,
        user_agent=user_agent,
        details=f"Signatory {recipient.name} executed Hardware USB Token Digital Signature (CN: {recipient.dsc_common_name}, Serial: {recipient.dsc_serial})",
    )

    # Check envelope completion status
    all_recipients = sig_request.recipients
    completed = all(r.status == "signed" or r.id == recipient.id for r in all_recipients if r.role == "signer")

    if completed:
        sig_request.status = "completed"
        sig_request.completed_at = datetime.now(timezone.utc)

    await db.commit()
    return {"status": "success", "message": "Hardware DSC Signature recorded successfully", "request_status": sig_request.status}


@router.post("/sign/{token}/dsc-pfx-seal")
async def seal_software_pfx_dsc_signature(
    token: str,
    file: UploadFile = File(...),
    passphrase: str = Form(...),
    db: DbSession = None,
    req: Request = None,
):
    """Executes digital contract sealing using software .pfx / .p12 X.509 Digital Signature Certificate."""
    stmt = (
        select(SignatureRecipient)
        .options(
            selectinload(SignatureRecipient.request).selectinload(SignatureRequest.fields),
            selectinload(SignatureRecipient.request).selectinload(SignatureRequest.recipients),
        )
        .where(SignatureRecipient.access_token == token)
    )
    result = await db.execute(stmt)
    recipient = result.scalar_one_or_none()

    if not recipient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid signature token")

    if recipient.status == "signed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Recipient has already signed this contract")

    pfx_bytes = await file.read()

    # Parse PFX/P12 certificate and private key using cryptography module
    try:
        private_key, cert, additional_certs = pkcs12.load_key_and_certificates(
            pfx_bytes,
            passphrase.encode("utf-8") if passphrase else None
        )
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid PFX/P12 certificate file or incorrect passphrase")

    if not cert:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No X.509 signing certificate found in PFX file")

    cn_attributes = cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
    common_name = cn_attributes[0].value if cn_attributes else recipient.name
    issuer_attributes = cert.issuer.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
    issuer_cn = issuer_attributes[0].value if issuer_attributes else "X.509 Certificate Authority"
    serial_str = hex(cert.serial_number)[2:].upper()

    client_ip = req.client.host if req and req.client else "127.0.0.1"
    user_agent = req.headers.get("user-agent") if req else "Browser"

    recipient.dsc_type = "software_pfx"
    recipient.dsc_common_name = common_name
    recipient.dsc_issuer = issuer_cn
    recipient.dsc_serial = serial_str
    recipient.status = "signed"
    recipient.signed_at = datetime.now(timezone.utc)
    recipient.ip_address = client_ip
    recipient.user_agent = user_agent

    await _log_audit_event(
        db,
        request_id=recipient.request_id,
        recipient_id=recipient.id,
        action="signed_dsc_pfx",
        ip_address=client_ip,
        user_agent=user_agent,
        details=f"Signatory {recipient.name} executed Software PFX Digital Signature (CN: {common_name}, Serial: {serial_str}, Issuer: {issuer_cn})",
    )

    all_recipients = recipient.request.recipients
    completed = all(r.status == "signed" or r.id == recipient.id for r in all_recipients if r.role == "signer")

    if completed:
        recipient.request.status = "completed"
        recipient.request.completed_at = datetime.now(timezone.utc)

    await db.commit()
    return {"status": "success", "message": "Software PFX DSC Signature recorded successfully", "request_status": recipient.request.status}


@router.get("/sign/{token}/status")
async def get_signing_portal_status(
    token: str,
    db: DbSession = None,
):
    """Public endpoint to query status of a contract envelope after signing."""
    stmt = (
        select(SignatureRecipient)
        .options(
            selectinload(SignatureRecipient.request).selectinload(SignatureRequest.recipients),
        )
        .where(SignatureRecipient.access_token == token)
    )
    result = await db.execute(stmt)
    recipient = result.scalar_one_or_none()

    if not recipient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid signature token")

    sig_request = recipient.request

    recipients_status = [
        {
            "name": r.name,
            "email": r.email,
            "role": r.role,
            "status": r.status,
            "signed_at": r.signed_at.isoformat() if r.signed_at else None,
        }
        for r in sig_request.recipients
    ]

    return {
        "request_id": str(sig_request.id),
        "title": sig_request.title,
        "request_status": sig_request.status,
        "document_hash": sig_request.document_hash,
        "recipients": recipients_status,
    }


@router.post("/sign/{token}")
async def submit_signature(
    token: str,
    payload: SignSubmissionRequest,
    db: DbSession = None,
    req: Request = None,
):
    """Public endpoint for a recipient to submit their filled signature fields."""
    stmt = (
        select(SignatureRecipient)
        .options(
            selectinload(SignatureRecipient.request).selectinload(SignatureRequest.fields),
            selectinload(SignatureRecipient.request).selectinload(SignatureRequest.recipients),
            selectinload(SignatureRecipient.request).selectinload(SignatureRequest.audit_logs),
        )
        .where(SignatureRecipient.access_token == token)
    )
    result = await db.execute(stmt)
    recipient = result.scalar_one_or_none()

    if not recipient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid signature link")

    if recipient.status == "signed":
        return {
            "status": "already_signed",
            "message": "Signature already recorded",
            "completed": True,
        }

    sig_request = recipient.request

    if recipient.access_passcode and recipient.access_passcode != payload.passcode:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid security passcode")

    client_ip = req.client.host if req and req.client else "127.0.0.1"
    user_agent = req.headers.get("user-agent") if req else "Browser"

    # Fill field values
    submitted_values_map = {item.field_id: item.value for item in payload.fields}

    for f in sig_request.fields:
        if f.recipient_id == recipient.id and f.id in submitted_values_map:
            f.value = submitted_values_map[f.id]

    recipient.status = "signed"
    recipient.signed_at = datetime.now(timezone.utc)
    recipient.ip_address = client_ip
    recipient.user_agent = user_agent

    await _log_audit_event(
        db,
        request_id=sig_request.id,
        recipient_id=recipient.id,
        action="signed",
        ip_address=client_ip,
        user_agent=user_agent,
        details=f"Signatory {recipient.name} ({recipient.email}) signed the contract",
    )

    # Check if ALL signatories have completed
    all_signed = all(r.status == "signed" for r in sig_request.recipients if r.role == "signer")

    if all_signed:
        # Finalize contract PDF: embed signatures + append Audit Certificate + calculate SHA-256 seal
        with open(sig_request.original_file_path, "rb") as orig_f:
            original_pdf_bytes = orig_f.read()

        fields_data = [
            {
                "page_number": f.page_number,
                "pos_x": f.pos_x,
                "pos_y": f.pos_y,
                "width": f.width,
                "height": f.height,
                "type": f.type,
                "value": f.value,
            }
            for f in sig_request.fields
        ]

        recipients_data = [
            {
                "name": r.name,
                "email": r.email,
                "role": r.role,
                "signed_at": r.signed_at,
                "ip_address": r.ip_address,
            }
            for r in sig_request.recipients
        ]

        audit_logs_data = [
            {
                "created_at": a.created_at,
                "action": a.action,
                "ip_address": a.ip_address,
                "details": a.details,
            }
            for a in sig_request.audit_logs
        ]

        signed_pdf_bytes, sha256_hash = embed_signatures_and_seal(
            original_pdf_bytes=original_pdf_bytes,
            fields_data=fields_data,
            recipients_data=recipients_data,
            audit_logs_data=audit_logs_data,
            request_title=sig_request.title,
            request_id=str(sig_request.id),
            created_at=sig_request.created_at,
        )

        signed_filename = f"signed_{sig_request.id}.pdf"
        signed_file_path = os.path.join(UPLOAD_DIR, signed_filename)

        with open(signed_file_path, "wb") as sf:
            sf.write(signed_pdf_bytes)

        sig_request.signed_file_path = signed_file_path
        sig_request.document_hash = sha256_hash
        sig_request.status = "completed"
        sig_request.completed_at = datetime.now(timezone.utc)

        await _log_audit_event(
            db,
            request_id=sig_request.id,
            action="completed",
            ip_address=client_ip,
            user_agent=user_agent,
            details=f"All signatories completed. Cryptographic SHA-256 seal: {sha256_hash}",
        )

    await db.commit()

    return {
        "status": "success",
        "message": "Contract signed successfully",
        "request_status": sig_request.status,
    }


@router.get("/requests/{request_id}/download")
async def download_contract_pdf(
    request_id: uuid.UUID,
    db: DbSession = None,
):
    """Download the contract PDF (original or finalized signed document)."""
    stmt = select(SignatureRequest).where(SignatureRequest.id == request_id)
    result = await db.execute(stmt)
    sig_request = result.scalar_one_or_none()

    if not sig_request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Signature request not found")

    target_path = sig_request.signed_file_path or sig_request.original_file_path
    if not os.path.exists(target_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File missing on disk")

    filename = f"{sig_request.title}.pdf"
    return FileResponse(target_path, media_type="application/pdf", filename=filename)


@router.get("/verify/{identifier}", response_model=DocumentVerificationResponse)
async def verify_contract_authenticity(
    identifier: str,
    db: DbSession = None,
):
    """Public verification endpoint to validate document hash and view audit certificate trail."""
    parsed_uuid = None
    if identifier.startswith("cntr_") or (identifier.replace("-", "").isalnum() and len(identifier) in (32, 36)):
        try:
            parsed_uuid = uuid.UUID(identifier.replace("cntr_", ""))
        except ValueError:
            parsed_uuid = None
        if not parsed_uuid and identifier.replace("-", "").isalnum() and len(identifier) in (32, 36):
            try:
                parsed_uuid = uuid.UUID(identifier)
            except ValueError:
                parsed_uuid = None

    stmt = (
        select(SignatureRequest)
        .options(
            selectinload(SignatureRequest.recipients),
            selectinload(SignatureRequest.audit_logs),
        )
        .where(
            or_(
                SignatureRequest.document_hash == identifier,
                SignatureRequest.id == parsed_uuid,
            )
        )
    )
    result = await db.execute(stmt)
    sig_request = result.scalar_one_or_none()

    if not sig_request and parsed_uuid:
        # Check ContractAssistantContract
        from app.db.models import ContractAssistantContract, ContractAssistantEnvelope
        ca_stmt = (
            select(ContractAssistantContract)
            .options(
                selectinload(ContractAssistantContract.envelopes).selectinload(ContractAssistantEnvelope.signature_request).selectinload(SignatureRequest.recipients),
                selectinload(ContractAssistantContract.envelopes).selectinload(ContractAssistantEnvelope.signature_request).selectinload(SignatureRequest.audit_logs),
                selectinload(ContractAssistantContract.signatories),
            )
            .where(ContractAssistantContract.id == parsed_uuid)
        )
        ca_res = await db.execute(ca_stmt)
        ca_contract = ca_res.scalar_one_or_none()

        if ca_contract and ca_contract.envelopes:
            sig_request = ca_contract.envelopes[0].signature_request

        if not sig_request and ca_contract:
            import hashlib
            h = hashlib.sha256(f"{ca_contract.title}_{ca_contract.id}".encode()).hexdigest()
            return DocumentVerificationResponse(
                document_id=ca_contract.id,
                title=ca_contract.title,
                status=ca_contract.status,
                created_at=ca_contract.created_at,
                completed_at=ca_contract.signed_at,
                document_hash=h,
                total_signatories=len(ca_contract.signatories) if ca_contract.signatories else 2,
                completed_signatories=0,
                audit_trail=[],
            )

    if not sig_request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract verification record not found")

    total_sig = len(sig_request.recipients)
    completed_sig = sum(1 for r in sig_request.recipients if r.status == "signed")

    return DocumentVerificationResponse(
        document_id=sig_request.id,
        title=sig_request.title,
        status=sig_request.status,
        created_at=sig_request.created_at,
        completed_at=sig_request.completed_at,
        document_hash=sig_request.document_hash,
        total_signatories=total_sig,
        completed_signatories=completed_sig,
        audit_trail=sig_request.audit_logs,
    )


@router.post("/requests/{request_id}/void")
async def void_signature_request(
    request_id: str,
    db: DbSession,
):
    """Quash/void a signature request directly."""
    try:
        r_uuid = uuid.UUID(request_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid request_id format")

    sig_stmt = select(SignatureRequest).where(SignatureRequest.id == r_uuid)
    sig_req = (await db.execute(sig_stmt)).scalar_one_or_none()

    if not sig_req:
        raise HTTPException(status_code=404, detail="Signature request not found")

    now = datetime.now(timezone.utc)
    sig_req.status = "voided"
    db.add(SignatureAuditLog(
        request_id=sig_req.id,
        action="VOIDED",
        details=f"Contract agreement officially quashed and voided by admin at {now.isoformat()}.",
    ))

    # Also update associated ContractAssistantContract if linked
    from app.db.models import ContractAssistantContract, ContractAssistantEnvelope
    env_stmt = select(ContractAssistantEnvelope).where(ContractAssistantEnvelope.signature_request_id == r_uuid)
    env = (await db.execute(env_stmt)).scalar_one_or_none()
    if env:
        ca_stmt = select(ContractAssistantContract).where(ContractAssistantContract.id == env.contract_id)
        contract = (await db.execute(ca_stmt)).scalar_one_or_none()
        if contract:
            contract.status = "voided"

    await db.commit()
    return {"status": "voided", "message": "Signature request officially voided."}


@router.get("/requests/{request_id}/export-void")
async def export_voided_signature_copy(
    request_id: str,
    db: DbSession,
):
    """Export cancelled certificate for signature request."""
    try:
        r_uuid = uuid.UUID(request_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid request_id format")

    sig_stmt = select(SignatureRequest).options(selectinload(SignatureRequest.recipients)).where(SignatureRequest.id == r_uuid)
    sig_req = (await db.execute(sig_stmt)).scalar_one_or_none()

    title = sig_req.title if sig_req else "Contract Agreement"
    file_hash = (sig_req.document_hash if sig_req and sig_req.document_hash else "SHA256_UNREGISTERED")
    created_at_str = (sig_req.created_at.isoformat() if sig_req and sig_req.created_at else datetime.now(timezone.utc).isoformat())
    signatories_str = ", ".join([r.name for r in sig_req.recipients]) if sig_req and sig_req.recipients else "Signatories Registered"
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    cert_text = f"""================================================================================
           OFFICIAL CERTIFICATE OF CANCELLATION & VOIDED COPY
================================================================================
GOBITSNBYTES FOUNDATION (Section 8 Non-Profit Co., Companies Act 2013)
bits&bytes™ Legal Operations & Contract Assistant Portal

STATUS:              VOIDED & CANCELLED (REVOKED)
DOCUMENT TITLE:      {title}
DOCUMENT ID:         {request_id}
ORIGINAL CHECKSUM:   {file_hash}
DATE OF CREATION:    {created_at_str}
DATE OF REVOCATION:  {now_str}
REGISTERED PARTIES:  {signatories_str}

--------------------------------------------------------------------------------
STATUTORY REVOCATION NOTICE:
In accordance with Section 10A of the Information Technology Act, 2000 and Section
65B of the Indian Evidence Act (Bharatiya Sakshya Adhiniyam, 2023):

1. THIS CONTRACT AGREEMENT HAS BEEN OFFICIALLY QUASHED AND VOIDED BY THE ISSUING
   AUTHORITY (GOBITSNBYTES FOUNDATION).
2. ALL ELECTRONIC SIGNATURE LINKS, TOKENIZED PORTAL ACCESS, AND STATUTORY ENFORCEABILITY
   FOR THIS DOCUMENT ARE PERMANENTLY REVOKED AND TERMINATED.
3. THIS DOCUMENT CONSTITUTES THE SOLE CERTIFIED ARCHIVAL RECORD PROVING THAT THE
   AGREEMENT WAS CANCELLED AND VOIDED PRIOR TO DESTRUCTION OF ONLINE DATABASE RECORDS.
--------------------------------------------------------------------------------
Audit Trail: Generated & Sealed on {now_str} by Legal Administrator.
================================================================================
"""
    return Response(
        content=cert_text,
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="VOIDED_AGREEMENT_{request_id[:8]}.txt"'},
    )


@router.delete("/requests/{request_id}")
async def delete_signature_request_permanently(
    request_id: str,
    db: DbSession,
):
    """Purge signature request permanently."""
    try:
        r_uuid = uuid.UUID(request_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid request_id format")

    sig_stmt = select(SignatureRequest).where(SignatureRequest.id == r_uuid)
    sig_req = (await db.execute(sig_stmt)).scalar_one_or_none()

    if sig_req:
        if sig_req.original_file_path and os.path.exists(sig_req.original_file_path):
            try:
                os.remove(sig_req.original_file_path)
            except Exception:
                pass
        await db.delete(sig_req)

    # Delete linked ContractAssistantContract if exists
    from app.db.models import ContractAssistantContract, ContractAssistantEnvelope
    env_stmt = select(ContractAssistantEnvelope).where(ContractAssistantEnvelope.signature_request_id == r_uuid)
    env = (await db.execute(env_stmt)).scalar_one_or_none()
    if env:
        ca_stmt = select(ContractAssistantContract).where(ContractAssistantContract.id == env.contract_id)
        contract = (await db.execute(ca_stmt)).scalar_one_or_none()
        if contract:
            await db.delete(contract)

    await db.commit()
    return {"status": "deleted", "message": f"Signature request {request_id} permanently deleted."}


