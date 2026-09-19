"""Volunteer and fork onboarding API.

Portal tokens are scoped to one participant. Internal case actions use the
existing IAM principal and never accept a portal token as reviewer authority.
"""

from datetime import datetime, timedelta, timezone
import html
import hashlib
from pathlib import Path
import shutil
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.db.models import (
    Fork,
    OnboardingCase,
    OnboardingDocument,
    OnboardingDocumentRevision,
    OnboardingParticipant,
    OnboardingReview,
    OnboardingReviewComment,
    OnboardingReviewThread,
    OnboardingRevision,
    SignatureRequest,
    User,
)
from app.dependencies import CurrentUserDep, DbSession
from app.iam.policy import require_permission
from app.iam.audit import write_audit_entry
from app.schemas.onboarding import (
    OnboardingCaseCreate,
    OnboardingCaseResponse,
    OnboardingCancelRequest,
    OnboardingCertificateCreate,
    OnboardingChangesRequest,
    OnboardingCompileRequest,
    OnboardingDeleteResponse,
    OnboardingDraftPatch,
    OnboardingDocumentResponse,
    OnboardingRemindResponse,
    OnboardingDocumentSubmit,
    OnboardingEditorResponse,
    OnboardingHQFieldsPatch,
    OnboardingParticipantResponse,
    OnboardingParticipantEmailUpdate,
    OnboardingPortalResponse,
    OnboardingPortalSubmit,
    OnboardingReviewCreate,
    OnboardingReviewThreadResponse,
    OnboardingTeammateCreate,
    OnboardingThreadCreate,
    OnboardingThreadReply,
    OnboardingThreadStatusUpdate,
)
from app.services.onboarding_documents import (
    TEMPLATE_MANIFEST,
    create_signature_request,
    hash_portal_token,
    new_portal_token,
    render_docx_to_pdf,
    storage_root,
    template_root,
    validate_age,
)
from app.services.semantic_ooxml import (
    annotate_package,
    derived_values,
    document_blocks,
    fields_for,
    package_hash,
    repack_docx,
    signature_markers,
    state_hash,
    template_hash,
    unpack_docx,
    validate_values,
)


router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

PARTICIPANT_EDITABLE_STATUSES = {"awaiting_completion", "draft", "changes_requested"}


def _portal_url(token: str) -> str:
    return f"{get_settings().nextauth_url}/onboarding/{token}"


def _document_response(document: OnboardingDocument, request: SignatureRequest | None = None) -> OnboardingDocumentResponse:
    url = None
    if request:
        signer = next((recipient for recipient in request.recipients if recipient.role != "organization"), None)
        if signer:
            url = f"{get_settings().nextauth_url}/sign/{signer.access_token}"
    return OnboardingDocumentResponse(
        id=document.id,
        document_key=document.document_key,
        template_filename=document.template_filename,
        status=document.status,
        signature_request_id=document.signature_request_id,
        signature_url=url,
        evidence_hash=document.evidence_hash,
        canonical_hash=document.canonical_hash,
        completed_at=document.completed_at,
        revision_id=document.revision_id,
        current_revision=document.current_revision,
        state_hash=document.state_hash,
        final_docx_hash=document.final_docx_hash,
        final_pdf_hash=document.final_pdf_hash,
    )


async def _load_case(db: DbSession, case_id: uuid.UUID) -> OnboardingCase:
    result = await db.execute(
        select(OnboardingCase)
        .options(
            selectinload(OnboardingCase.participants).selectinload(OnboardingParticipant.documents),
            selectinload(OnboardingCase.documents),
            selectinload(OnboardingCase.reviews),
        )
        .where(OnboardingCase.id == case_id)
    )
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Onboarding case not found")
    return case


async def _sync_signature_states(db: DbSession, case: OnboardingCase) -> None:
    for document in case.documents:
        if not document.signature_request_id:
            continue
        request = await db.get(SignatureRequest, document.signature_request_id)
        if not request:
            continue
        if request.status == "completed":
            document.status = "completed"
            document.canonical_hash = request.document_hash
            document.completed_at = request.completed_at
            document.finalized_at = request.completed_at
            if request.signed_file_path and Path(request.signed_file_path).is_file():
                document.final_pdf_hash = hashlib.sha256(Path(request.signed_file_path).read_bytes()).hexdigest()
        elif request.status in {"voided", "expired"}:
            document.status = request.status
    if case.documents and all(document.status in {"completed", "accepted"} for document in case.documents):
        case.status = "completed"


def _case_response(case: OnboardingCase) -> OnboardingCaseResponse:
    participants = []
    for participant in case.participants:
        documents = [_document_response(document) for document in participant.documents]
        participants.append(
            OnboardingParticipantResponse(
                id=participant.id,
                role=participant.role,
                name=participant.name,
                email=participant.email,
                date_of_birth=participant.date_of_birth,
                is_minor=participant.is_minor,
                status=participant.status,
                submitted_at=participant.submitted_at,
                documents=documents,
                portal_url=None,
            )
        )
    return OnboardingCaseResponse(
        id=case.id,
        kind=case.kind,
        title=case.title,
        status=case.status,
        fork_id=case.fork_id,
        case_data=case.case_data,
        created_by=case.created_by,
        reviewer_id=case.reviewer_id,
        current_revision_id=case.current_revision_id,
        created_at=case.created_at,
        updated_at=case.updated_at,
        participants=participants,
        documents=[_document_response(document) for document in case.documents],
        reviews=[
            {
                "id": review.id,
                "document_id": review.document_id,
                "reviewer_id": review.reviewer_id,
                "decision": review.decision,
                "note": review.note,
                "created_at": review.created_at,
            }
            for review in case.reviews
        ],
    )


async def _find_portal_participant(db: DbSession, token: str) -> OnboardingParticipant:
    participant = (
        await db.execute(
            select(OnboardingParticipant)
            .options(selectinload(OnboardingParticipant.case).selectinload(OnboardingCase.documents), selectinload(OnboardingParticipant.documents))
            .where(OnboardingParticipant.portal_token_hash == hash_portal_token(token))
        )
    ).scalar_one_or_none()
    if not participant:
        raise HTTPException(status_code=404, detail="This onboarding link is invalid or expired")
    expires_at = participant.token_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=404, detail="This onboarding link is invalid or expired")
    return participant


def _thread_response(thread: OnboardingReviewThread) -> OnboardingReviewThreadResponse:
    return OnboardingReviewThreadResponse(
        id=thread.id,
        document_id=thread.document_id,
        field_id=thread.field_id,
        block_id=thread.block_id,
        quote=thread.quote,
        status=thread.status,
        created_at=thread.created_at,
        comments=[
            {
                "id": comment.id,
                "author_kind": comment.author_kind,
                "author_ref": comment.author_ref,
                "body": comment.body,
                "created_at": comment.created_at,
            }
            for comment in thread.comments
        ],
    )


async def _load_document_for_editor(db: DbSession, document_id: uuid.UUID) -> OnboardingDocument:
    document = (
        await db.execute(
            select(OnboardingDocument)
            .options(
                selectinload(OnboardingDocument.participant),
                selectinload(OnboardingDocument.case),
                selectinload(OnboardingDocument.review_threads).selectinload(OnboardingReviewThread.comments),
            )
            .where(OnboardingDocument.id == document_id)
        )
    ).scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Onboarding document not found")
    return document


def _write_revision_package(
    *,
    document: OnboardingDocument,
    revision: int,
    values: dict,
) -> tuple[str, str, list[str]]:
    revision_root = storage_root() / str(document.case_id) / str(document.id) / "revisions" / str(revision)
    package_dir = revision_root / "package"
    if document.draft_package_path and Path(document.draft_package_path).is_dir():
        shutil.copytree(document.draft_package_path, package_dir)
    else:
        template = template_root() / document.template_filename
        if not template.is_file():
            raise FileNotFoundError(f"Onboarding template is missing: {document.template_filename}")
        unpack_docx(template, package_dir)
    missing = annotate_package(package_dir, document.document_key, values)
    return str(package_dir), package_hash(package_dir), missing


def _compile_ooxml_source(document: OnboardingDocument, values: dict) -> tuple[Path, Path]:
    if not document.draft_package_path or not Path(document.draft_package_path).is_dir():
        raise RuntimeError("The document has no materialized OOXML draft")
    root = storage_root().resolve()
    final_root = (root / str(document.case_id) / str(document.id) / "final").resolve()
    if root not in final_root.parents:
        raise RuntimeError("Invalid onboarding storage path")
    package_dir = final_root / "package"
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(document.draft_package_path, package_dir)
    missing = annotate_package(package_dir, document.document_key, values)
    if missing:
        raise RuntimeError(f"Template is missing semantic anchors: {', '.join(missing)}")
    docx_path = final_root / f"{document.document_key}-revision-{document.current_revision}.docx"
    repack_docx(package_dir, docx_path)
    return package_dir, docx_path


async def _persist_revision(
    db: DbSession,
    *,
    document: OnboardingDocument,
    values: dict,
    actor_kind: str,
    actor_ref: str | None,
) -> OnboardingDocumentRevision:
    revision_number = document.current_revision + 1
    package_path, package_digest, missing = await run_in_threadpool(
        _write_revision_package,
        document=document,
        revision=revision_number,
        values=values,
    )
    if missing:
        raise RuntimeError(f"Template is missing semantic anchors: {', '.join(missing)}")
    digest = state_hash(
        document_id=str(document.id),
        revision=revision_number,
        previous_hash=document.state_hash,
        values=values,
        package_digest=package_digest,
    )
    revision = OnboardingDocumentRevision(
        document_id=document.id,
        revision=revision_number,
        field_values=values,
        package_path=package_path,
        package_hash=package_digest,
        previous_state_hash=document.state_hash,
        state_hash=digest,
        actor_kind=actor_kind,
        actor_ref=actor_ref,
    )
    db.add(revision)
    document.current_revision = revision_number
    document.field_values = values
    document.draft_package_path = package_path
    document.state_hash = digest
    if not document.template_hash:
        document.template_hash = template_hash(template_root() / document.template_filename)
    return revision


async def _ensure_initial_revision(db: DbSession, document: OnboardingDocument) -> None:
    if document.current_revision > 0 and document.draft_package_path:
        return
    await _persist_revision(
        db,
        document=document,
        values=dict(document.field_values or {}),
        actor_kind="system",
        actor_ref=None,
    )
    if document.status == "awaiting_completion":
        document.status = "draft"
    await db.commit()


def _invite_email(name: str, title: str, token: str) -> tuple[str, str]:
    url = html.escape(_portal_url(token), quote=True)
    subject = f"Complete your onboarding: {title}"
    body = f"<p>Hello <strong>{html.escape(name)}</strong>,</p><p>Complete your onboarding packet securely:</p><p><a href=\"{url}\">Open onboarding portal</a></p><p>This link is scoped to your documents and expires in 30 days.</p>"
    return subject, body


def _cancellation_email(name: str, title: str, reason: str | None = None) -> tuple[str, str]:
    subject = f"Onboarding workflow cancelled: {title}"
    body = (
        f"<p>Hello <strong>{html.escape(name)}</strong>,</p>"
        f"<p>The onboarding workflow for <strong>{html.escape(title)}</strong> has been cancelled and removed by Bits&Bytes Foundation HQ.</p>"
        + (f"<p><strong>Reason:</strong> {html.escape(reason)}</p>" if reason else "")
        + "<p>Any pending signature requests, portal links, or document drafts associated with this workflow are now void. No further action is required from you.</p>"
    )
    return subject, body


def _reminder_email(name: str, title: str, link: str, is_signing: bool = False) -> tuple[str, str]:
    url = html.escape(link, quote=True)
    if is_signing:
        subject = f"Reminder: Signature required for {title}"
        action_text = "Review and sign document"
        desc = "Your signature is required to complete this onboarding document. Please review and sign at the link below:"
    else:
        subject = f"Reminder: Complete your onboarding for {title}"
        action_text = "Open onboarding portal"
        desc = "This is a friendly reminder to complete your onboarding packet securely:"
    body = (
        f"<p>Hello <strong>{html.escape(name)}</strong>,</p>"
        f"<p>{desc}</p>"
        f"<p><a href=\"{url}\" style=\"display:inline-block;background-color:#fc920d;color:#120f0a;padding:10px 18px;font-weight:bold;text-decoration:none;border:2px solid #120f0a;\">{action_text}</a></p>"
        f"<p>Direct link: <a href=\"{url}\">{url}</a></p>"
    )
    return subject, body



@router.post("/cases", response_model=OnboardingCaseResponse, status_code=status.HTTP_201_CREATED)
async def create_case(
    payload: OnboardingCaseCreate,
    background_tasks: BackgroundTasks,
    db: DbSession,
    current_user: CurrentUserDep,
) -> OnboardingCaseResponse:
    await require_permission(db, current_user, "onboarding.write")
    try:
        age, is_minor = validate_age(payload.participant.date_of_birth)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if is_minor and not payload.participant.parent:
        raise HTTPException(status_code=422, detail="A parent or guardian is required for participants under 18")
    if payload.kind == "fork" and not payload.fork_id and not payload.fork_name:
        raise HTTPException(status_code=422, detail="A fork id or fork name is required for fork onboarding")

    if payload.fork_id and not await db.get(Fork, payload.fork_id):
        raise HTTPException(status_code=404, detail="Fork not found")
    if payload.reviewer_id:
        if payload.reviewer_id == current_user.user_id:
            raise HTTPException(status_code=422, detail="The case creator cannot be the assigned reviewer")
        if not await db.get(User, payload.reviewer_id):
            raise HTTPException(status_code=404, detail="Assigned reviewer not found")

    case = OnboardingCase(
        kind=payload.kind,
        title=payload.title,
        created_by=current_user.user_id,
        reviewer_id=payload.reviewer_id,
        fork_id=payload.fork_id,
        case_data={"fork_name": payload.fork_name, "participant_age": age, "parent_required": is_minor},
    )
    db.add(case)
    await db.flush()
    case_revision = OnboardingRevision(
        case_id=case.id,
        number=1,
        created_by=current_user.user_id,
        template_snapshot={key: TEMPLATE_MANIFEST[key]["source_hash"] for key in (["volunteer"] if payload.kind == "volunteer" else ["fork_application", "fork_agreement"])},
    )
    db.add(case_revision)
    await db.flush()
    case.current_revision_id = case_revision.id

    token, token_hash = new_portal_token()
    participant = OnboardingParticipant(
        case_id=case.id,
        role="participant",
        name=payload.participant.name,
        email=str(payload.participant.email),
        date_of_birth=payload.participant.date_of_birth,
        is_minor=is_minor,
        portal_token_hash=token_hash,
        token_expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        revision_id=case_revision.id,
    )
    db.add(participant)
    await db.flush()

    document_keys = ["volunteer"]
    if payload.kind == "fork":
        document_keys += ["fork_application", "fork_agreement"]
    for key in document_keys:
        manifest = TEMPLATE_MANIFEST[key]
        defaults = {
            "bnb.volunteer.full_name": participant.name,
            "bnb.volunteer.date_of_birth": participant.date_of_birth,
            "bnb.volunteer.email": participant.email,
        } if key == "volunteer" else {
            "bnb.fork.application.lead_name": participant.name,
            "bnb.fork.application.date_of_birth": participant.date_of_birth,
            "bnb.fork.application.email": participant.email,
            "bnb.fork.application.fork_name": payload.fork_name or "",
            "bnb.fork.agreement.lead_name": participant.name,
            "bnb.fork.agreement.date_of_birth": participant.date_of_birth,
            "bnb.fork.agreement.email": participant.email,
            "bnb.fork.agreement.fork_name": payload.fork_name or "",
        }
        allowed_ids = {field["id"] for field in fields_for(key)}
        db.add(OnboardingDocument(case_id=case.id, participant_id=participant.id, document_key=key, template_filename=manifest["template"], revision_id=case_revision.id, field_values={field_id: value for field_id, value in defaults.items() if field_id in allowed_ids and value}))

    parent_token = None
    if is_minor and payload.participant.parent:
        parent_token, parent_hash = new_portal_token()
        parent = OnboardingParticipant(
            case_id=case.id,
            role="parent",
            name=payload.participant.parent.name,
            email=str(payload.participant.parent.email),
            is_minor=False,
            portal_token_hash=parent_hash,
            token_expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            revision_id=case_revision.id,
        )
        db.add(parent)
        await db.flush()
        db.add(OnboardingDocument(
            case_id=case.id,
            participant_id=parent.id,
            revision_id=case_revision.id,
            document_key="parent_consent",
            template_filename=TEMPLATE_MANIFEST["parent_consent"]["template"],
            field_values={
                "bnb.parent.minor_name": participant.name,
                "bnb.parent.minor_dob": participant.date_of_birth,
                "bnb.parent.guardian_name": parent.name,
                "bnb.parent.guardian_email": parent.email,
            },
        ))

    await write_audit_entry(
        db,
        current_user.user_id,
        "onboarding.case_created",
        "onboarding_case",
        str(case.id),
        {"kind": case.kind, "revision_id": str(case.current_revision_id) if case.current_revision_id else None},
    )
    await db.commit()
    settings = get_settings()
    if settings.smtp_host and settings.smtp_user and settings.smtp_pass:
        from app.routers.meetings import send_smtp_email
        subject, body = _invite_email(participant.name, case.title, token)
        background_tasks.add_task(send_smtp_email, settings, [participant.email], subject, body)
        if parent_token and payload.participant.parent:
            p_subject, p_body = _invite_email(payload.participant.parent.name, case.title, parent_token)
            background_tasks.add_task(send_smtp_email, settings, [str(payload.participant.parent.email)], p_subject, p_body)
    loaded = await _load_case(db, case.id)
    response = _case_response(loaded)
    for participant_response in response.participants:
        if participant_response.id == participant.id:
            participant_response.portal_url = _portal_url(token)
        elif parent_token and participant_response.role == "parent":
            participant_response.portal_url = _portal_url(parent_token)
    return response


@router.get("/cases", response_model=list[OnboardingCaseResponse])
async def list_cases(db: DbSession, current_user: CurrentUserDep) -> list[OnboardingCaseResponse]:
    await require_permission(db, current_user, "onboarding.read")
    rows = (await db.execute(select(OnboardingCase).order_by(OnboardingCase.created_at.desc()))).scalars().all()
    # The signing engine does not know about onboarding, so signed documents only
    # converge on a read.  Without this the dashboard sits on "signing" forever.
    cases = [await _load_case(db, row.id) for row in rows]
    for case in cases:
        await _sync_signature_states(db, case)
    await db.commit()
    return [_case_response(case) for case in cases]


@router.get("/cases/{case_id}", response_model=OnboardingCaseResponse)
async def get_case(case_id: uuid.UUID, db: DbSession, current_user: CurrentUserDep) -> OnboardingCaseResponse:
    await require_permission(db, current_user, "onboarding.read")
    case = await _load_case(db, case_id)
    await _sync_signature_states(db, case)
    await db.commit()
    return _case_response(case)


@router.patch("/cases/{case_id}/participants/{participant_id}/email")
async def update_participant_email(
    case_id: uuid.UUID,
    participant_id: uuid.UUID,
    payload: OnboardingParticipantEmailUpdate,
    background_tasks: BackgroundTasks,
    db: DbSession,
    current_user: CurrentUserDep,
) -> dict[str, str]:
    """Correct an untouched primary participant's email and rotate their portal link."""
    await require_permission(db, current_user, "onboarding.write")
    case = await _load_case(db, case_id)
    participant = next((item for item in case.participants if item.id == participant_id), None)
    if not participant:
        raise HTTPException(status_code=404, detail="Onboarding participant not found")
    if participant.role != "participant":
        raise HTTPException(status_code=403, detail="Only the primary volunteer or fork lead email can be updated here")
    if not participant.documents or participant.status != "invited" or any(
        document.status != "awaiting_completion" or document.signature_request_id
        for document in participant.documents
    ):
        raise HTTPException(status_code=409, detail="Email can only be updated before this participant starts signing")
    duplicate = (
        await db.execute(
            select(OnboardingParticipant.id).where(
                OnboardingParticipant.case_id == case.id,
                OnboardingParticipant.email == str(payload.email),
                OnboardingParticipant.id != participant.id,
            )
        )
    ).scalar_one_or_none()
    if duplicate:
        raise HTTPException(status_code=409, detail="That email is already used by another participant in this case")

    token, token_hash = new_portal_token()
    participant.email = str(payload.email)
    participant.portal_token_hash = token_hash
    participant.token_expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    await db.commit()

    settings = get_settings()
    if settings.smtp_host and settings.smtp_user and settings.smtp_pass:
        from app.routers.meetings import send_smtp_email

        subject, body = _invite_email(participant.name, case.title, token)
        background_tasks.add_task(send_smtp_email, settings, [participant.email], subject, body)
    return {"participant_id": str(participant.id), "email": participant.email, "portal_url": _portal_url(token)}


@router.post("/cases/{case_id}/participants/{participant_id}/resend")
async def resend_participant_invite(
    case_id: uuid.UUID,
    participant_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: DbSession,
    current_user: CurrentUserDep,
) -> dict[str, str | bool]:
    """Send a fresh, rotated portal link to an invited onboarding participant."""
    await require_permission(db, current_user, "onboarding.write")
    case = await _load_case(db, case_id)
    participant = next((item for item in case.participants if item.id == participant_id), None)
    if not participant:
        raise HTTPException(status_code=404, detail="Onboarding participant not found")
    if not participant.documents or participant.status != "invited" or any(
        document.status != "awaiting_completion" or document.signature_request_id
        for document in participant.documents
    ):
        raise HTTPException(status_code=409, detail="Only untouched onboarding invites can be resent")

    token, token_hash = new_portal_token()
    participant.portal_token_hash = token_hash
    participant.token_expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    await db.commit()

    settings = get_settings()
    email_sent = bool(settings.smtp_host and settings.smtp_user and settings.smtp_pass)
    if email_sent:
        from app.routers.meetings import send_smtp_email

        subject, body = _invite_email(participant.name, case.title, token)
        background_tasks.add_task(send_smtp_email, settings, [participant.email], subject, body)
    return {"participant_id": str(participant.id), "email": participant.email, "portal_url": _portal_url(token), "email_sent": email_sent}


@router.post("/cases/{case_id}/cancel", response_model=OnboardingCaseResponse)
async def cancel_case(
    case_id: uuid.UUID,
    payload: OnboardingCancelRequest,
    db: DbSession,
    current_user: CurrentUserDep,
) -> OnboardingCaseResponse:
    """Revoke portal access and pending signature envelopes for a withdrawn case."""
    await require_permission(db, current_user, "onboarding.write")
    case = await _load_case(db, case_id)
    if case.status in {"approved", "rejected", "revoked", "completed"}:
        raise HTTPException(status_code=409, detail="This onboarding case can no longer be cancelled")
    now = datetime.now(timezone.utc)
    for participant in case.participants:
        participant.token_expires_at = now
        if participant.status != "submitted":
            participant.status = "revoked"
    request_ids = [document.signature_request_id for document in case.documents if document.signature_request_id]
    if request_ids:
        requests = (await db.execute(select(SignatureRequest).options(selectinload(SignatureRequest.recipients)).where(SignatureRequest.id.in_(request_ids)))).scalars().all()
        for request in requests:
            if request.status not in {"completed", "voided", "expired"}:
                request.status = "voided"
                for recipient in request.recipients:
                    if recipient.status not in {"signed", "declined"}:
                        recipient.status = "declined"
                    recipient.otp_code = recipient.otp_hash = None
                    recipient.otp_attempts = 0
                    recipient.otp_expires_at = recipient.otp_verified_at = None
    for document in case.documents:
        if document.status not in {"completed", "signed", "accepted"}:
            document.status = "revoked"
    case.status = "revoked"
    case.case_data = {**(case.case_data or {}), "cancelled_at": now.isoformat(), "cancellation_reason": payload.reason}
    await write_audit_entry(db, current_user.user_id, "onboarding.case_cancelled", "onboarding_case", str(case.id), {"reason": payload.reason, "revision_id": str(case.current_revision_id) if case.current_revision_id else None})
    await db.commit()
    return _case_response(await _load_case(db, case.id))


@router.delete("/cases/{case_id}", response_model=OnboardingDeleteResponse)
async def delete_case(
    case_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: DbSession,
    current_user: CurrentUserDep,
) -> OnboardingDeleteResponse:
    """Permanently delete an onboarding workflow, void pending envelopes, and notify/remind signers."""
    await require_permission(db, current_user, "onboarding.write")
    case = await _load_case(db, case_id)

    # 1. Void any associated signature requests
    request_ids = [doc.signature_request_id for doc in case.documents if doc.signature_request_id]
    signature_recipients: list[dict[str, str]] = []
    if request_ids:
        requests = (
            await db.execute(
                select(SignatureRequest)
                .options(selectinload(SignatureRequest.recipients))
                .where(SignatureRequest.id.in_(request_ids))
            )
        ).scalars().all()
        for req in requests:
            if req.status not in {"completed", "voided", "expired"}:
                req.status = "voided"
                for recipient in req.recipients:
                    if recipient.status not in {"signed", "declined"}:
                        recipient.status = "declined"
                    recipient.otp_code = recipient.otp_hash = None
                    recipient.otp_attempts = 0
                    recipient.otp_expires_at = recipient.otp_verified_at = None
                    if recipient.email:
                        signature_recipients.append({"name": recipient.name, "email": recipient.email})

    # 2. Collect unique signers/participants to notify of workflow deletion
    seen_emails: set[str] = set()
    signers_to_notify: list[dict[str, str]] = []
    for participant in case.participants:
        if participant.email and participant.email.lower() not in seen_emails:
            seen_emails.add(participant.email.lower())
            signers_to_notify.append({"name": participant.name, "email": participant.email})
    for sig in signature_recipients:
        if sig["email"].lower() not in seen_emails:
            seen_emails.add(sig["email"].lower())
            signers_to_notify.append(sig)

    # 3. Notify signers via email if SMTP is configured
    settings = get_settings()
    if settings.smtp_host and settings.smtp_user and settings.smtp_pass:
        from app.routers.meetings import send_smtp_email
        for signer in signers_to_notify:
            subject, body = _cancellation_email(signer["name"], case.title)
            background_tasks.add_task(send_smtp_email, settings, [signer["email"]], subject, body)

    # 4. Clean up disk assets
    case_dir = storage_root() / str(case.id)
    if case_dir.exists():
        shutil.rmtree(case_dir, ignore_errors=True)

    # 5. Write audit entry
    notified_list = [s["email"] for s in signers_to_notify]
    await write_audit_entry(
        db,
        current_user.user_id,
        "onboarding.case_deleted",
        "onboarding_case",
        str(case.id),
        {"title": case.title, "kind": case.kind, "notified_signers": notified_list},
    )

    # 6. Delete case and cascade to all child records in DB
    await db.delete(case)
    await db.commit()

    return OnboardingDeleteResponse(
        ok=True,
        message=f"Onboarding workflow '{case.title}' deleted.",
        id=str(case_id),
        notified=notified_list,
    )


@router.post("/cases/{case_id}/remind", response_model=OnboardingRemindResponse)
async def remind_case_signers(
    case_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: DbSession,
    current_user: CurrentUserDep,
) -> OnboardingRemindResponse:
    """Send reminder emails to all pending participants and document signers."""
    await require_permission(db, current_user, "onboarding.write")
    case = await _load_case(db, case_id)
    settings = get_settings()
    now = datetime.now(timezone.utc)
    reminded: list[str] = []
    seen: set[str] = set()

    # 1. Pending invited participants
    for participant in case.participants:
        if participant.status == "invited" and participant.email and participant.email.lower() not in seen:
            token, token_hash = new_portal_token()
            participant.portal_token_hash = token_hash
            participant.token_expires_at = now + timedelta(days=30)
            seen.add(participant.email.lower())
            reminded.append(participant.email)
            if settings.smtp_host and settings.smtp_user and settings.smtp_pass:
                from app.routers.meetings import send_smtp_email
                subject, body = _reminder_email(participant.name, case.title, _portal_url(token), is_signing=False)
                background_tasks.add_task(send_smtp_email, settings, [participant.email], subject, body)

    # 2. Pending signature recipients
    signing_docs = [doc for doc in case.documents if doc.status == "signing" and doc.signature_request_id]
    if signing_docs:
        req_ids = [doc.signature_request_id for doc in signing_docs]
        requests = (
            await db.execute(
                select(SignatureRequest)
                .options(selectinload(SignatureRequest.recipients))
                .where(SignatureRequest.id.in_(req_ids))
            )
        ).scalars().all()
        for req in requests:
            for rec in req.recipients:
                if rec.status == "pending" and rec.email and rec.email.lower() not in seen:
                    seen.add(rec.email.lower())
                    reminded.append(rec.email)
                    sign_url = f"{settings.nextauth_url}/sign/{rec.access_token}"
                    if settings.smtp_host and settings.smtp_user and settings.smtp_pass:
                        from app.routers.meetings import send_smtp_email
                        subject, body = _reminder_email(rec.name, case.title, sign_url, is_signing=True)
                        background_tasks.add_task(send_smtp_email, settings, [rec.email], subject, body)

    if reminded:
        await write_audit_entry(
            db,
            current_user.user_id,
            "onboarding.reminders_sent",
            "onboarding_case",
            str(case.id),
            {"reminded": reminded, "count": len(reminded)},
        )
        await db.commit()

    return OnboardingRemindResponse(
        ok=True,
        reminded_count=len(reminded),
        reminded=reminded,
        email_sent=bool(settings.smtp_host and settings.smtp_user and settings.smtp_pass),
    )


@router.post("/cases/{case_id}/documents/{document_id}/remind", response_model=OnboardingRemindResponse)
async def remind_document_signers(
    case_id: uuid.UUID,
    document_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: DbSession,
    current_user: CurrentUserDep,
) -> OnboardingRemindResponse:
    """Send reminder emails to pending signers of a specific onboarding document."""
    await require_permission(db, current_user, "onboarding.write")
    document = await _load_document_for_editor(db, document_id)
    if document.case_id != case_id:
        raise HTTPException(status_code=404, detail="Onboarding document not found")
    settings = get_settings()
    reminded: list[str] = []
    seen: set[str] = set()

    if document.status == "signing" and document.signature_request_id:
        request = (
            await db.execute(
                select(SignatureRequest)
                .options(selectinload(SignatureRequest.recipients))
                .where(SignatureRequest.id == document.signature_request_id)
            )
        ).scalar_one_or_none()
        if request:
            for rec in request.recipients:
                if rec.status == "pending" and rec.email and rec.email.lower() not in seen:
                    seen.add(rec.email.lower())
                    reminded.append(rec.email)
                    sign_url = f"{settings.nextauth_url}/sign/{rec.access_token}"
                    if settings.smtp_host and settings.smtp_user and settings.smtp_pass:
                        from app.routers.meetings import send_smtp_email
                        subject, body = _reminder_email(rec.name, document.case.title, sign_url, is_signing=True)
                        background_tasks.add_task(send_smtp_email, settings, [rec.email], subject, body)
    elif document.participant and document.participant.status == "invited":
        token, token_hash = new_portal_token()
        document.participant.portal_token_hash = token_hash
        document.participant.token_expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        reminded.append(document.participant.email)
        if settings.smtp_host and settings.smtp_user and settings.smtp_pass:
            from app.routers.meetings import send_smtp_email
            subject, body = _reminder_email(document.participant.name, document.case.title, _portal_url(token), is_signing=False)
            background_tasks.add_task(send_smtp_email, settings, [document.participant.email], subject, body)

    if reminded:
        await write_audit_entry(
            db,
            current_user.user_id,
            "onboarding.document_reminded",
            "onboarding_document",
            str(document.id),
            {"reminded": reminded, "document_key": document.document_key},
        )
        await db.commit()

    return OnboardingRemindResponse(
        ok=True,
        reminded_count=len(reminded),
        reminded=reminded,
        email_sent=bool(settings.smtp_host and settings.smtp_user and settings.smtp_pass),
    )



@router.get("/public/{token}/documents/{document_id}/editor", response_model=OnboardingEditorResponse)
async def get_public_document_editor(token: str, document_id: uuid.UUID, db: DbSession) -> OnboardingEditorResponse:
    participant = await _find_portal_participant(db, token)
    document = await _load_document_for_editor(db, document_id)
    if document.participant_id != participant.id:
        raise HTTPException(status_code=404, detail="Onboarding document not found")
    try:
        await _ensure_initial_revision(db, document)
        sections = await run_in_threadpool(document_blocks, template_root() / document.template_filename, document.document_key)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    editable = document.status in PARTICIPANT_EDITABLE_STATUSES
    return OnboardingEditorResponse(
        document=_document_response(document),
        title=document.document_key.replace("_", " ").title(),
        fields=fields_for(document.document_key, editor="participant"),
        sections=sections,
        values=document.field_values,
        threads=[_thread_response(thread) for thread in document.review_threads],
        editable=editable,
        can_submit=editable,
    )


@router.patch("/public/{token}/documents/{document_id}/draft", response_model=OnboardingEditorResponse)
async def patch_public_document_draft(token: str, document_id: uuid.UUID, payload: OnboardingDraftPatch, db: DbSession) -> OnboardingEditorResponse:
    participant = await _find_portal_participant(db, token)
    document = await _load_document_for_editor(db, document_id)
    if document.participant_id != participant.id:
        raise HTTPException(status_code=404, detail="Onboarding document not found")
    if document.status not in PARTICIPANT_EDITABLE_STATUSES:
        raise HTTPException(status_code=409, detail="This document is locked for review")
    await _ensure_initial_revision(db, document)
    if payload.base_revision != document.current_revision:
        raise HTTPException(status_code=409, detail={"message": "The document changed in another session", "current_revision": document.current_revision})
    errors = validate_values(document.document_key, payload.values, editor="participant")
    if errors:
        raise HTTPException(status_code=422, detail={"message": "Some fields are invalid", "fields": errors})
    values = {**(document.field_values or {}), **payload.values}
    if values != document.field_values:
        try:
            await _persist_revision(db, document=document, values=values, actor_kind="participant", actor_ref=str(participant.id))
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            await db.rollback()
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        changed = set(payload.values)
        for thread in document.review_threads:
            if thread.status == "open" and thread.field_id in changed:
                thread.status = "addressed"
        document.status = "draft"
        await db.commit()
        document = await _load_document_for_editor(db, document.id)
    sections = await run_in_threadpool(document_blocks, template_root() / document.template_filename, document.document_key)
    return OnboardingEditorResponse(
        document=_document_response(document), title=document.document_key.replace("_", " ").title(),
        fields=fields_for(document.document_key, editor="participant"), sections=sections,
        values=document.field_values, threads=[_thread_response(thread) for thread in document.review_threads],
        editable=True, can_submit=True,
    )


@router.post("/public/{token}/documents/{document_id}/submit", response_model=OnboardingEditorResponse)
async def submit_public_document(token: str, document_id: uuid.UUID, payload: OnboardingDocumentSubmit, db: DbSession) -> OnboardingEditorResponse:
    participant = await _find_portal_participant(db, token)
    document = await _load_document_for_editor(db, document_id)
    if document.participant_id != participant.id:
        raise HTTPException(status_code=404, detail="Onboarding document not found")
    if not payload.confirmed_identity:
        raise HTTPException(status_code=422, detail="Confirm your identity before requesting review")
    if document.status not in PARTICIPANT_EDITABLE_STATUSES:
        raise HTTPException(status_code=409, detail="This document is already under review")
    await _ensure_initial_revision(db, document)
    if payload.base_revision != document.current_revision:
        raise HTTPException(status_code=409, detail={"message": "Save or reload the latest revision before submitting", "current_revision": document.current_revision})
    errors = validate_values(document.document_key, document.field_values or {}, editor="participant", final=True)
    if errors:
        raise HTTPException(status_code=422, detail={"message": "Complete the required fields", "fields": errors})
    document.status = "review_requested"
    participant.status = "under_review"
    participant.submitted_at = datetime.now(timezone.utc)
    participant.verified_at = datetime.now(timezone.utc)
    participant.answers = {**participant.answers, document.document_key: document.field_values}
    await db.commit()
    document = await _load_document_for_editor(db, document.id)
    sections = await run_in_threadpool(document_blocks, template_root() / document.template_filename, document.document_key)
    return OnboardingEditorResponse(
        document=_document_response(document), title=document.document_key.replace("_", " ").title(),
        fields=fields_for(document.document_key, editor="participant"), sections=sections,
        values=document.field_values, threads=[_thread_response(thread) for thread in document.review_threads],
        editable=False, can_submit=False,
    )


@router.post("/public/{token}/review-threads/{thread_id}/comments", response_model=OnboardingReviewThreadResponse)
async def reply_to_review_thread(token: str, thread_id: uuid.UUID, payload: OnboardingThreadReply, db: DbSession) -> OnboardingReviewThreadResponse:
    participant = await _find_portal_participant(db, token)
    thread = (
        await db.execute(
            select(OnboardingReviewThread)
            .options(selectinload(OnboardingReviewThread.document), selectinload(OnboardingReviewThread.comments))
            .where(OnboardingReviewThread.id == thread_id)
        )
    ).scalar_one_or_none()
    if not thread or thread.document.participant_id != participant.id:
        raise HTTPException(status_code=404, detail="Review thread not found")
    db.add(OnboardingReviewComment(thread_id=thread.id, author_kind="participant", author_ref=str(participant.id), body=payload.body))
    if thread.status == "open":
        thread.status = "addressed"
    await db.commit()
    thread = (await db.execute(select(OnboardingReviewThread).options(selectinload(OnboardingReviewThread.comments)).where(OnboardingReviewThread.id == thread.id))).scalar_one()
    return _thread_response(thread)


@router.get("/public/{token}", response_model=OnboardingPortalResponse)
async def get_portal(token: str, db: DbSession) -> OnboardingPortalResponse:
    participant = await _find_portal_participant(db, token)
    request_ids = [document.signature_request_id for document in participant.documents if document.signature_request_id]
    requests = (await db.execute(select(SignatureRequest).options(selectinload(SignatureRequest.recipients)).where(SignatureRequest.id.in_(request_ids)))).scalars().all() if request_ids else []
    requests_by_id = {request.id: request for request in requests}
    return OnboardingPortalResponse(
        case_id=participant.case.id,
        case_title=participant.case.title,
        case_kind=participant.case.kind,
        participant=OnboardingParticipantResponse(
            id=participant.id,
            role=participant.role,
            name=participant.name,
            email=participant.email,
            date_of_birth=participant.date_of_birth,
            is_minor=participant.is_minor,
            status=participant.status,
            submitted_at=participant.submitted_at,
            documents=[_document_response(document, requests_by_id.get(document.signature_request_id)) for document in participant.documents],
        ),
        documents=[_document_response(document, requests_by_id.get(document.signature_request_id)) for document in participant.documents],
        field_manifest={key: value["fields"] for key, value in TEMPLATE_MANIFEST.items() if any(document.document_key == key for document in participant.documents)},
    )


@router.post("/public/{token}/submit", response_model=OnboardingPortalResponse)
async def submit_portal(token: str, payload: OnboardingPortalSubmit, db: DbSession) -> OnboardingPortalResponse:
    participant = await _find_portal_participant(db, token)
    if not payload.confirmed_identity:
        raise HTTPException(status_code=422, detail="Confirm that the information belongs to you before submitting")
    answer_sets = payload.document_answers or ({participant.documents[0].document_key: payload.answers} if len(participant.documents) == 1 and payload.answers else {})
    expected_keys = {document.document_key for document in participant.documents if document.status in PARTICIPANT_EDITABLE_STATUSES}
    if set(answer_sets) != expected_keys:
        raise HTTPException(status_code=422, detail="Submit answers for every editable onboarding document")
    document_errors: dict[str, dict[str, str]] = {}
    for document in participant.documents:
        if document.document_key not in answer_sets:
            continue
        values = {**(document.field_values or {}), **answer_sets[document.document_key]}
        errors = validate_values(document.document_key, values, editor="participant", final=True)
        if errors:
            document_errors[document.document_key] = errors
    if document_errors:
        raise HTTPException(status_code=422, detail={"message": "Complete the required fields", "documents": document_errors})
    participant.verified_at = datetime.now(timezone.utc)
    participant.submitted_at = datetime.now(timezone.utc)
    try:
        for document in participant.documents:
            if document.document_key not in answer_sets:
                continue
            await _ensure_initial_revision(db, document)
            values = {**(document.field_values or {}), **answer_sets[document.document_key]}
            if values != document.field_values:
                await _persist_revision(db, document=document, values=values, actor_kind="participant", actor_ref=str(participant.id))
            document.status = "review_requested"
        participant.answers = answer_sets
        participant.status = "under_review"
        participant.case.status = "under_review"
        await db.commit()
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        await db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return await get_portal(token, db)


@router.post("/public/{token}/teammates", response_model=OnboardingPortalResponse, status_code=status.HTTP_201_CREATED)
async def add_teammate(token: str, payload: OnboardingTeammateCreate, db: DbSession, background_tasks: BackgroundTasks) -> OnboardingPortalResponse:
    lead = await _find_portal_participant(db, token)
    if lead.role != "participant" or lead.case.kind != "fork" or lead.status != "submitted":
        raise HTTPException(status_code=403, detail="Only a submitted fork lead can invite teammates")
    try:
        _, is_minor = validate_age(payload.date_of_birth)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if is_minor and not payload.parent:
        raise HTTPException(status_code=422, detail="A parent or guardian is required for a minor teammate")
    teammate_token, teammate_hash = new_portal_token()
    teammate = OnboardingParticipant(case_id=lead.case_id, role="teammate", name=payload.name, email=str(payload.email), date_of_birth=payload.date_of_birth, is_minor=is_minor, portal_token_hash=teammate_hash, token_expires_at=datetime.now(timezone.utc) + timedelta(days=30))
    db.add(teammate)
    await db.flush()
    db.add(OnboardingDocument(case_id=lead.case_id, participant_id=teammate.id, document_key="volunteer", template_filename=TEMPLATE_MANIFEST["volunteer"]["template"]))
    if is_minor and payload.parent:
        parent_token, parent_hash = new_portal_token()
        parent = OnboardingParticipant(case_id=lead.case_id, role="parent", name=payload.parent.name, email=str(payload.parent.email), is_minor=False, portal_token_hash=parent_hash, token_expires_at=datetime.now(timezone.utc) + timedelta(days=30))
        db.add(parent)
        await db.flush()
        db.add(OnboardingDocument(case_id=lead.case_id, participant_id=parent.id, document_key="parent_consent", template_filename=TEMPLATE_MANIFEST["parent_consent"]["template"]))
    await db.commit()
    settings = get_settings()
    if settings.smtp_host and settings.smtp_user and settings.smtp_pass:
        from app.routers.meetings import send_smtp_email
        subject, body = _invite_email(payload.name, lead.case.title, teammate_token)
        background_tasks.add_task(send_smtp_email, settings, [str(payload.email)], subject, body)
        if is_minor and payload.parent:
            parent_subject, parent_body = _invite_email(payload.parent.name, lead.case.title, parent_token)
            background_tasks.add_task(send_smtp_email, settings, [str(payload.parent.email)], parent_subject, parent_body)
    return await get_portal(token, db)


@router.get("/cases/{case_id}/documents/{document_id}/editor", response_model=OnboardingEditorResponse)
async def get_staff_document_editor(case_id: uuid.UUID, document_id: uuid.UUID, db: DbSession, current_user: CurrentUserDep) -> OnboardingEditorResponse:
    await require_permission(db, current_user, "onboarding.review")
    document = await _load_document_for_editor(db, document_id)
    if document.case_id != case_id:
        raise HTTPException(status_code=404, detail="Onboarding document not found")
    await _sync_signature_states(db, await _load_case(db, case_id))
    await db.commit()
    await db.refresh(document)
    await _ensure_initial_revision(db, document)
    sections = await run_in_threadpool(document_blocks, template_root() / document.template_filename, document.document_key)
    return OnboardingEditorResponse(
        document=_document_response(document), title=document.document_key.replace("_", " ").title(),
        fields=fields_for(document.document_key), sections=sections, values=document.field_values,
        threads=[_thread_response(thread) for thread in document.review_threads],
        editable=document.status not in {"signing", "compiling", "completed", "voided"}, can_submit=False,
        can_compile=document.status == "approved" and not any(thread.status != "resolved" for thread in document.review_threads),
    )


@router.patch("/cases/{case_id}/documents/{document_id}/draft", response_model=OnboardingEditorResponse)
async def patch_staff_document_fields(case_id: uuid.UUID, document_id: uuid.UUID, payload: OnboardingHQFieldsPatch, db: DbSession, current_user: CurrentUserDep) -> OnboardingEditorResponse:
    await require_permission(db, current_user, "onboarding.review")
    document = await _load_document_for_editor(db, document_id)
    if document.case_id != case_id:
        raise HTTPException(status_code=404, detail="Onboarding document not found")
    if document.status in {"signing", "compiling", "completed", "voided"}:
        raise HTTPException(status_code=409, detail="This document can no longer be edited")
    await _ensure_initial_revision(db, document)
    if payload.base_revision != document.current_revision:
        raise HTTPException(status_code=409, detail={"message": "The document changed in another session", "current_revision": document.current_revision})
    errors = validate_values(document.document_key, payload.values, editor="hq")
    if errors:
        raise HTTPException(status_code=422, detail={"message": "Some fields are invalid", "fields": errors})
    values = {**(document.field_values or {}), **payload.values}
    if values != document.field_values:
        try:
            await _persist_revision(db, document=document, values=values, actor_kind="hq", actor_ref=str(current_user.user_id))
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            await db.rollback()
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        await db.commit()
    return await get_staff_document_editor(case_id, document_id, db, current_user)


@router.post("/cases/{case_id}/documents/{document_id}/review-threads", response_model=OnboardingReviewThreadResponse, status_code=status.HTTP_201_CREATED)
async def create_review_thread(case_id: uuid.UUID, document_id: uuid.UUID, payload: OnboardingThreadCreate, db: DbSession, current_user: CurrentUserDep) -> OnboardingReviewThreadResponse:
    await require_permission(db, current_user, "onboarding.review")
    document = await _load_document_for_editor(db, document_id)
    if document.case_id != case_id:
        raise HTTPException(status_code=404, detail="Onboarding document not found")
    if document.status not in {"review_requested", "changes_requested"}:
        raise HTTPException(status_code=409, detail="Review comments can only be added during an active review")
    if not payload.field_id and not payload.block_id:
        raise HTTPException(status_code=422, detail="Anchor the review to a field or document block")
    valid_fields = {field["id"] for field in fields_for(document.document_key)}
    sections = await run_in_threadpool(document_blocks, template_root() / document.template_filename, document.document_key)
    valid_blocks = {block["id"] for section in sections for block in section["blocks"]}
    if payload.field_id and payload.field_id not in valid_fields:
        raise HTTPException(status_code=422, detail="Unknown document field")
    if payload.block_id and payload.block_id not in valid_blocks:
        raise HTTPException(status_code=422, detail="Unknown document block")
    thread = OnboardingReviewThread(document_id=document.id, field_id=payload.field_id, block_id=payload.block_id, quote=payload.quote, created_by=current_user.user_id)
    db.add(thread)
    await db.flush()
    db.add(OnboardingReviewComment(thread_id=thread.id, author_kind="hq", author_ref=str(current_user.user_id), body=payload.body))
    await db.commit()
    thread = (await db.execute(select(OnboardingReviewThread).options(selectinload(OnboardingReviewThread.comments)).where(OnboardingReviewThread.id == thread.id))).scalar_one()
    return _thread_response(thread)


@router.post("/cases/{case_id}/review-threads/{thread_id}/comments", response_model=OnboardingReviewThreadResponse)
async def reply_to_review_thread_as_staff(case_id: uuid.UUID, thread_id: uuid.UUID, payload: OnboardingThreadReply, db: DbSession, current_user: CurrentUserDep) -> OnboardingReviewThreadResponse:
    await require_permission(db, current_user, "onboarding.review")
    thread = (await db.execute(select(OnboardingReviewThread).options(selectinload(OnboardingReviewThread.document), selectinload(OnboardingReviewThread.comments)).where(OnboardingReviewThread.id == thread_id))).scalar_one_or_none()
    if not thread or thread.document.case_id != case_id:
        raise HTTPException(status_code=404, detail="Review thread not found")
    db.add(OnboardingReviewComment(thread_id=thread.id, author_kind="hq", author_ref=str(current_user.user_id), body=payload.body))
    await db.commit()
    thread = (await db.execute(select(OnboardingReviewThread).options(selectinload(OnboardingReviewThread.comments)).where(OnboardingReviewThread.id == thread.id))).scalar_one()
    return _thread_response(thread)


@router.patch("/cases/{case_id}/review-threads/{thread_id}", response_model=OnboardingReviewThreadResponse)
async def update_review_thread_status(case_id: uuid.UUID, thread_id: uuid.UUID, payload: OnboardingThreadStatusUpdate, db: DbSession, current_user: CurrentUserDep) -> OnboardingReviewThreadResponse:
    await require_permission(db, current_user, "onboarding.review")
    thread = (await db.execute(select(OnboardingReviewThread).options(selectinload(OnboardingReviewThread.document), selectinload(OnboardingReviewThread.comments)).where(OnboardingReviewThread.id == thread_id))).scalar_one_or_none()
    if not thread or thread.document.case_id != case_id:
        raise HTTPException(status_code=404, detail="Review thread not found")
    thread.status = payload.status
    thread.resolved_by = current_user.user_id if payload.status == "resolved" else None
    thread.resolved_at = datetime.now(timezone.utc) if payload.status == "resolved" else None
    await db.commit()
    return _thread_response(thread)


@router.post("/cases/{case_id}/documents/{document_id}/request-changes", response_model=OnboardingEditorResponse)
async def request_document_changes(case_id: uuid.UUID, document_id: uuid.UUID, payload: OnboardingChangesRequest, db: DbSession, current_user: CurrentUserDep) -> OnboardingEditorResponse:
    await require_permission(db, current_user, "onboarding.review")
    document = await _load_document_for_editor(db, document_id)
    if document.case_id != case_id:
        raise HTTPException(status_code=404, detail="Onboarding document not found")
    if document.status != "review_requested":
        raise HTTPException(status_code=409, detail="Only a submitted review can be returned")
    if payload.note:
        thread = OnboardingReviewThread(document_id=document.id, block_id="document", quote=None, created_by=current_user.user_id)
        db.add(thread)
        await db.flush()
        db.add(OnboardingReviewComment(thread_id=thread.id, author_kind="hq", author_ref=str(current_user.user_id), body=payload.note))
    elif not any(thread.status == "open" for thread in document.review_threads):
        raise HTTPException(status_code=422, detail="Add an open review comment before requesting changes")
    document.status = "changes_requested"
    if document.participant:
        document.participant.status = "changes_requested"
    await db.commit()
    return await get_staff_document_editor(case_id, document_id, db, current_user)


@router.post("/cases/{case_id}/documents/{document_id}/approve", response_model=OnboardingEditorResponse)
async def approve_document_review(case_id: uuid.UUID, document_id: uuid.UUID, db: DbSession, current_user: CurrentUserDep) -> OnboardingEditorResponse:
    await require_permission(db, current_user, "onboarding.review")
    document = await _load_document_for_editor(db, document_id)
    if document.case_id != case_id:
        raise HTTPException(status_code=404, detail="Onboarding document not found")
    if document.case.created_by == current_user.user_id:
        raise HTTPException(status_code=403, detail="The case creator cannot approve their own onboarding case")
    if document.status != "review_requested":
        raise HTTPException(status_code=409, detail="Only a submitted review can be approved")
    unresolved = [thread for thread in document.review_threads if thread.status != "resolved"]
    if unresolved:
        raise HTTPException(status_code=409, detail="Resolve every review thread before approval")
    document.status = "approved"
    case = await _load_case(db, case_id)
    packet_documents = [item for item in case.documents if item.document_key != "fork_certificate"]
    if packet_documents and all(item.status == "approved" for item in packet_documents):
        case.status = "audit_approved" if case.kind == "fork" else "approved"
        case.approved_at = datetime.now(timezone.utc)
        case.approved_by = current_user.user_id
    await db.commit()
    return await get_staff_document_editor(case_id, document_id, db, current_user)


@router.post("/cases/{case_id}/documents/{document_id}/compile", response_model=OnboardingEditorResponse)
async def compile_approved_document(case_id: uuid.UUID, document_id: uuid.UUID, payload: OnboardingCompileRequest, db: DbSession, current_user: CurrentUserDep) -> OnboardingEditorResponse:
    """Freeze an approved revision, render it, and open its cryptographic signing request."""
    await require_permission(db, current_user, "onboarding.review")
    document = await _load_document_for_editor(db, document_id)
    if document.case_id != case_id:
        raise HTTPException(status_code=404, detail="Onboarding document not found")
    if document.status != "approved":
        raise HTTPException(status_code=409, detail="Only an approved document can be compiled")
    if payload.base_revision != document.current_revision:
        raise HTTPException(status_code=409, detail={"message": "Compile the latest approved revision", "current_revision": document.current_revision})
    if any(thread.status != "resolved" for thread in document.review_threads):
        raise HTTPException(status_code=409, detail="Resolve every review thread before compilation")
    errors = validate_values(document.document_key, document.field_values or {}, editor="all", final=True)
    if errors:
        raise HTTPException(status_code=422, detail={"message": "Complete required document fields before compilation", "fields": errors})
    participant = document.participant
    if not participant:
        raise HTTPException(status_code=409, detail="The document has no participant signer")
    hq_user = await db.get(User, current_user.user_id)
    if not hq_user or not hq_user.email:
        raise HTTPException(status_code=409, detail="The HQ signer needs an email address")

    role = "guardian" if participant.role == "parent" else "lead" if document.document_key.startswith("fork_") else "subject"
    signature_fields = [field for field in fields_for(document.document_key) if field["type"] == "signature"]
    marker_values = (
        dict(document.field_values or {})
        | derived_values(document.document_key, participant_name=participant.name)
        | signature_markers(document.document_key)
    )
    try:
        _, docx_path = await run_in_threadpool(_compile_ooxml_source, document, marker_values)
        pdf_path = await run_in_threadpool(render_docx_to_pdf, docx_path, docx_path.parent)
        signer_specs = [{"name": participant.name, "email": participant.email, "role": role}]
        if any(field["editable_by"] == "hq" for field in signature_fields):
            signer_specs.append({"name": hq_user.display_name, "email": hq_user.email, "role": "organization", "allowed_sig_type": "email_only"})
        request = await create_signature_request(
            db,
            case=document.case,
            document=document,
            pdf_path=pdf_path,
            signer_specs=signer_specs,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        await db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    document.source_docx_path = str(docx_path)
    document.filled_docx_path = str(docx_path)
    document.source_pdf_path = str(pdf_path)
    document.final_docx_hash = hashlib.sha256(docx_path.read_bytes()).hexdigest()
    document.signature_request_id = request.id
    document.status = "signing"
    document.hq_signed_at = None
    await db.commit()
    return await get_staff_document_editor(case_id, document_id, db, current_user)


@router.post("/cases/{case_id}/review", response_model=OnboardingCaseResponse)
async def review_case(case_id: uuid.UUID, payload: OnboardingReviewCreate, db: DbSession, current_user: CurrentUserDep) -> OnboardingCaseResponse:
    await require_permission(db, current_user, "onboarding.review")
    case = await _load_case(db, case_id)
    await _sync_signature_states(db, case)
    if case.created_by == current_user.user_id:
        raise HTTPException(status_code=403, detail="The case creator cannot review or approve their own case")
    if payload.document_id and not any(document.id == payload.document_id for document in case.documents):
        raise HTTPException(status_code=404, detail="Document is not part of this case")
    if case.reviewer_id and case.reviewer_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Only the assigned reviewer can decide this case")
    review = OnboardingReview(case_id=case.id, document_id=payload.document_id, reviewer_id=current_user.user_id, decision=payload.decision, note=payload.note)
    db.add(review)
    case.reviews.append(review)
    case.reviewer_id = current_user.user_id
    if payload.document_id:
        document = next(document for document in case.documents if document.id == payload.document_id)
        document.status = "accepted" if payload.decision == "accepted" else payload.decision
    elif payload.decision == "accepted":
        for document in case.documents:
            if document.status == "signed":
                document.status = "accepted"
    elif payload.decision == "rejected":
        case.status = "rejected"
    if payload.decision == "accepted" and all(document.status in {"signed", "accepted"} for document in case.documents):
        case.status = "approved"
        case.approved_at = datetime.now(timezone.utc)
        case.approved_by = current_user.user_id
    await db.commit()
    return _case_response(await _load_case(db, case.id))


@router.post("/cases/{case_id}/certificate")
async def create_certificate(case_id: uuid.UUID, payload: OnboardingCertificateCreate, db: DbSession, current_user: CurrentUserDep) -> dict:
    await require_permission(db, current_user, "onboarding.certificate")
    case = await _load_case(db, case_id)
    if case.kind != "fork" or case.status != "audit_approved":
        raise HTTPException(status_code=409, detail="The full fork packet audit must be approved before issuing Form 3")
    if any(item.document_key == "fork_certificate" for item in case.documents):
        raise HTTPException(status_code=409, detail="Form 3 has already been issued for this case")
    lead = next((item for item in case.participants if item.role == "participant"), None)
    if not lead:
        raise HTTPException(status_code=409, detail="Fork lead is missing")
    application = next((item for item in case.documents if item.document_key == "fork_application"), None)
    agreement = next((item for item in case.documents if item.document_key == "fork_agreement"), None)
    document = OnboardingDocument(
        case_id=case.id,
        participant_id=lead.id,
        document_key="fork_certificate",
        template_filename=TEMPLATE_MANIFEST["fork_certificate"]["template"],
        status="draft",
    )
    db.add(document)
    await db.flush()
    values = {
        "bnb.fork.certificate.certificate_no": f"FRC-{datetime.now(timezone.utc).year}-{str(case.id)[:8].upper()}",
        "bnb.fork.certificate.fork_name": case.case_data.get("fork_name") or (application.field_values.get("bnb.fork.application.fork_name") if application else "Fork"),
        "bnb.fork.certificate.lead_name": lead.name,
        "bnb.fork.certificate.location": application.field_values.get("bnb.fork.application.location", "") if application else "",
        "bnb.fork.certificate.recognition_date": datetime.now(timezone.utc).date().isoformat(),
        "bnb.fork.certificate.agreement_ref": agreement.field_values.get("bnb.fork.agreement.agreement_ref", "") if agreement else "",
        "bnb.fork.certificate.director_names": f"{payload.director_one_name}; {payload.director_two_name}",
    }
    try:
        await _persist_revision(db, document=document, values=values, actor_kind="hq", actor_ref=str(current_user.user_id))
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        await db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    case.case_data = {
        **case.case_data,
        "certificate_signers": [
            {"name": payload.director_one_name, "email": str(payload.director_one_email)},
            {"name": payload.director_two_name, "email": str(payload.director_two_email)},
        ],
    }
    case.status = "certificate_issued"
    await db.commit()
    return {"case_id": str(case.id), "document_id": str(document.id), "status": document.status}
