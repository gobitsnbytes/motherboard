"""
FastAPI APIRouter for digital signature contracts (bnb-signatures).
"""

from datetime import datetime, timedelta, timezone
import hashlib
import os
import uuid
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, Response
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.db.models import SignatureAuditLog, SignatureField, SignatureRecipient, SignatureRequest, User
from app.dependencies import DbSession, get_current_user
from app.iam.principal import ResolvedPrincipal
from app.schemas.signatures import (
    DocumentVerificationResponse,
    FieldCreate,
    FieldResponse,
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
            "status": recipient.status,
            "requires_passcode": bool(recipient.access_passcode),
        },
        "previews": previews,
        "fields": recipient_fields,
    }


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
    stmt = (
        select(SignatureRequest)
        .options(
            selectinload(SignatureRequest.recipients),
            selectinload(SignatureRequest.audit_logs),
        )
        .where(
            or_(
                SignatureRequest.document_hash == identifier,
                SignatureRequest.id == (uuid.UUID(identifier) if identifier.replace("-", "").isalnum() and len(identifier) in (32, 36) else None),
            )
        )
    )
    result = await db.execute(stmt)
    sig_request = result.scalar_one_or_none()

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
