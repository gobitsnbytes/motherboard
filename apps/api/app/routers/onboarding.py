"""Volunteer and fork onboarding API.

Portal tokens are scoped to one participant. Internal case actions use the
existing IAM principal and never accept a portal token as reviewer authority.
"""

from datetime import datetime, timedelta, timezone
import html
import hashlib
import shutil
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.db.models import (
    Fork,
    OnboardingCase,
    OnboardingDocument,
    OnboardingParticipant,
    OnboardingReview,
    SignatureRequest,
)
from app.dependencies import CurrentUserDep, DbSession
from app.iam.policy import require_permission
from app.schemas.onboarding import (
    OnboardingCaseCreate,
    OnboardingCaseResponse,
    OnboardingCertificateCreate,
    OnboardingDocumentResponse,
    OnboardingParticipantResponse,
    OnboardingPortalResponse,
    OnboardingPortalSubmit,
    OnboardingReviewCreate,
    OnboardingTeammateCreate,
)
from app.services.onboarding_documents import (
    TEMPLATE_MANIFEST,
    _append_evidence_section,
    create_signature_request,
    hash_portal_token,
    materialize_document,
    new_portal_token,
    render_docx_to_pdf,
    storage_root,
    template_root,
    validate_age,
)


router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


def _portal_url(token: str) -> str:
    return f"{get_settings().nextauth_url}/onboarding/{token}"


def _document_response(document: OnboardingDocument, request: SignatureRequest | None = None) -> OnboardingDocumentResponse:
    url = None
    if request:
        signer = next((recipient for recipient in request.recipients if recipient.role == "signer"), None)
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
            document.status = "signed"
            document.canonical_hash = request.document_hash
            document.completed_at = request.completed_at
        elif request.status in {"voided", "expired"}:
            document.status = request.status
    if case.documents and all(document.status in {"signed", "accepted"} for document in case.documents):
        if case.status not in {"approved", "rejected"}:
            case.status = "ready_for_review"


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


def _invite_email(name: str, title: str, token: str) -> tuple[str, str]:
    url = html.escape(_portal_url(token), quote=True)
    subject = f"Complete your onboarding: {title}"
    body = f"<p>Hello <strong>{html.escape(name)}</strong>,</p><p>Complete your onboarding packet securely:</p><p><a href=\"{url}\">Open onboarding portal</a></p><p>This link is scoped to your documents and expires in 30 days.</p>"
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

    case = OnboardingCase(
        kind=payload.kind,
        title=payload.title,
        created_by=current_user.user_id,
        fork_id=payload.fork_id,
        case_data={"fork_name": payload.fork_name, "participant_age": age, "parent_required": is_minor},
    )
    db.add(case)
    await db.flush()

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
    )
    db.add(participant)
    await db.flush()

    document_keys = ["volunteer"]
    if payload.kind == "fork":
        document_keys += ["fork_application", "fork_agreement"]
    for key in document_keys:
        manifest = TEMPLATE_MANIFEST[key]
        db.add(OnboardingDocument(case_id=case.id, participant_id=participant.id, document_key=key, template_filename=manifest["template"]))

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
        )
        db.add(parent)
        await db.flush()
        db.add(OnboardingDocument(case_id=case.id, participant_id=parent.id, document_key="parent_consent", template_filename=TEMPLATE_MANIFEST["parent_consent"]["template"]))

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
    return [_case_response(await _load_case(db, row.id)) for row in rows]


@router.get("/cases/{case_id}", response_model=OnboardingCaseResponse)
async def get_case(case_id: uuid.UUID, db: DbSession, current_user: CurrentUserDep) -> OnboardingCaseResponse:
    await require_permission(db, current_user, "onboarding.read")
    case = await _load_case(db, case_id)
    await _sync_signature_states(db, case)
    await db.commit()
    return _case_response(case)


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
    if participant.status == "submitted" and participant.submitted_at:
        raise HTTPException(status_code=409, detail="This onboarding packet has already been submitted")
    if len(payload.answers) > 40 or any(len(key) > 100 or (isinstance(value, str) and len(value) > 2000) for key, value in payload.answers.items()):
        raise HTTPException(status_code=422, detail="Onboarding answers exceed the allowed size")
    values = dict(payload.answers)
    values.setdefault("full_name", participant.name)
    values.setdefault("date_of_birth", participant.date_of_birth)
    if participant.role == "parent":
        values.setdefault("parent_name", participant.name)
        values.setdefault("parent_email", participant.email)
    participant.answers = values
    participant.status = "submitted"
    participant.verified_at = datetime.now(timezone.utc)
    participant.submitted_at = datetime.now(timezone.utc)
    try:
        for document in participant.documents:
            if document.status == "awaiting_completion":
                await materialize_document(db, case=participant.case, document=document, participant=participant, values=values)
        participant.case.status = "awaiting_signatures"
        await db.commit()
    except (FileNotFoundError, RuntimeError) as exc:
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


@router.post("/cases/{case_id}/review", response_model=OnboardingCaseResponse)
async def review_case(case_id: uuid.UUID, payload: OnboardingReviewCreate, db: DbSession, current_user: CurrentUserDep) -> OnboardingCaseResponse:
    await require_permission(db, current_user, "onboarding.review")
    case = await _load_case(db, case_id)
    await _sync_signature_states(db, case)
    if case.created_by == current_user.user_id:
        raise HTTPException(status_code=403, detail="The case creator cannot review or approve their own case")
    if payload.document_id and not any(document.id == payload.document_id for document in case.documents):
        raise HTTPException(status_code=404, detail="Document is not part of this case")
    review = OnboardingReview(case_id=case.id, document_id=payload.document_id, reviewer_id=current_user.user_id, decision=payload.decision, note=payload.note)
    db.add(review)
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
    if case.kind != "fork" or case.status != "approved":
        raise HTTPException(status_code=409, detail="A fork certificate requires an approved fork onboarding case")
    if any(document.document_key == "fork_certificate" for document in case.documents):
        raise HTTPException(status_code=409, detail="A fork certificate has already been initiated")
    lead = next((participant for participant in case.participants if participant.role == "participant"), None)
    if not lead:
        raise HTTPException(status_code=409, detail="Fork lead is missing")
    document = OnboardingDocument(case_id=case.id, participant_id=None, document_key="fork_certificate", template_filename=TEMPLATE_MANIFEST["fork_certificate"]["template"], status="awaiting_signatures")
    db.add(document)
    await db.flush()
    folder = storage_root() / str(case.id) / str(document.id)
    folder.mkdir(parents=True, exist_ok=True)
    template = template_root() / TEMPLATE_MANIFEST["fork_certificate"]["template"]
    source = folder / template.name
    filled = folder / f"filled_{template.name}"
    shutil.copyfile(template, source)
    values = {"fork_name": case.case_data.get("fork_name") or "Fork", "lead_name": lead.name, "directors": f"{payload.director_one_name}; {payload.director_two_name}", "certificate_date": datetime.now(timezone.utc).date().isoformat()}
    _append_evidence_section(source, filled, values)
    pdf = render_docx_to_pdf(filled, folder)
    document.source_docx_path = str(source)
    document.filled_docx_path = str(filled)
    document.source_pdf_path = str(pdf)
    document.evidence_hash = hashlib.sha256(filled.read_bytes()).hexdigest()
    document.field_values = values
    request = await create_signature_request(db, case=case, document=document, pdf_path=pdf, signer_specs=[{"name": payload.director_one_name, "email": str(payload.director_one_email)}, {"name": payload.director_two_name, "email": str(payload.director_two_email)}], values=values, include_legal=True)
    document.signature_request_id = request.id
    await db.commit()
    return {"case_id": str(case.id), "document_id": str(document.id), "signature_request_id": str(request.id), "status": document.status}
