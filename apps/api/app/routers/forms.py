"""Staff form builder and anonymous public form submission endpoints."""
from datetime import datetime, timedelta, timezone
import os
import re
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from app.database import get_sessionmaker

from app.db.models import PublicForm, PublicFormSubmission, PublicFormUpload
from app.dependencies import DbSession, get_current_user
from app.iam.principal import ResolvedPrincipal
from app.schemas.forms import FormCreate, FormSubmissionCreate, FormSubmissionResponse, FormUpdate

router = APIRouter(prefix="/api/forms", tags=["forms"])
UPLOAD_DIR = os.path.join(os.getcwd(), "data", "forms")
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_FILES_PER_SUBMISSION = 5
ALLOWED_UPLOAD_TYPES = {"application/pdf", "image/jpeg", "image/png", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
_cleanup_scheduler = None


async def purge_expired_uploads() -> None:
    """Delete expired files and their metadata; runs daily in the API process."""
    async with get_sessionmaker()() as db:
        expired = (await db.execute(select(PublicFormUpload).where(PublicFormUpload.expires_at <= datetime.now(timezone.utc)))).scalars().all()
        for upload in expired:
            if os.path.isfile(upload.storage_path):
                os.remove(upload.storage_path)
            await db.delete(upload)
        await db.commit()


async def start_form_cleanup() -> None:
    global _cleanup_scheduler
    if _cleanup_scheduler:
        return
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    _cleanup_scheduler = AsyncIOScheduler()
    _cleanup_scheduler.add_job(purge_expired_uploads, "interval", days=1, id="public-form-upload-purge", replace_existing=True)
    _cleanup_scheduler.start()
    await purge_expired_uploads()


async def stop_form_cleanup() -> None:
    global _cleanup_scheduler
    if _cleanup_scheduler:
        _cleanup_scheduler.shutdown(wait=False)
        _cleanup_scheduler = None


def _staff_form(form: PublicForm) -> dict:
    return {"id": str(form.id), "title": form.title, "slug": form.slug, "description_markdown": form.description_markdown, "blocks": form.blocks, "is_published": form.is_published, "created_at": form.created_at, "updated_at": form.updated_at}


def _public_form(form: PublicForm) -> dict:
    return {"title": form.title, "slug": form.slug, "description_markdown": form.description_markdown, "blocks": form.blocks}


def _form_fields(form: PublicForm) -> dict[str, dict]:
    """Return answerable blocks keyed by ID, ignoring presentational blocks."""
    return {
        block.get("id"): block
        for block in form.blocks
        if isinstance(block, dict)
        and isinstance(block.get("id"), str)
        and block.get("type") not in {"heading", "paragraph", "divider", "consent"}
    }


def _validate_submission(form: PublicForm, answers: dict) -> None:
    fields = _form_fields(form)
    unknown = set(answers) - set(fields)
    if unknown:
        raise HTTPException(status_code=422, detail="This response contains questions that are not part of the form")
    for field_id, block in fields.items():
        answer = answers.get(field_id)
        missing = answer is None or answer == "" or answer == []
        if block.get("required") and block.get("type") != "file" and missing:
            raise HTTPException(status_code=422, detail=f"Please complete: {block.get('label', 'required question')}")
        if block.get("type") in {"choice", "select"} and answer not in (None, "") and answer not in block.get("options", []):
            raise HTTPException(status_code=422, detail=f"Choose a listed option for: {block.get('label', 'question')}")
        if block.get("type") == "multichoice" and answer not in (None, ""):
            if not isinstance(answer, list) or any(value not in block.get("options", []) for value in answer):
                raise HTTPException(status_code=422, detail=f"Choose listed options for: {block.get('label', 'question')}")


def _answer_labels(form: PublicForm, answers: dict) -> dict[str, str]:
    fields = _form_fields(form)
    return {field_id: fields.get(field_id, {}).get("label", "Question removed") for field_id in answers}


@router.get("", response_model=list[dict])
async def list_forms(db: DbSession, current_user: ResolvedPrincipal = Depends(get_current_user)):
    statement = select(PublicForm).order_by(PublicForm.updated_at.desc())
    if not current_user.is_super_admin:
        statement = statement.where(PublicForm.created_by == current_user.user_id)
    rows = (await db.execute(statement)).scalars().all()
    return [_staff_form(row) for row in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_form(payload: FormCreate, db: DbSession, current_user: ResolvedPrincipal = Depends(get_current_user)):
    form = PublicForm(**payload.model_dump(), created_by=current_user.user_id)
    db.add(form)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="That form slug is already in use")
    await db.refresh(form)
    return _staff_form(form)


@router.put("/{form_id}")
async def update_form(form_id: uuid.UUID, payload: FormUpdate, db: DbSession, current_user: ResolvedPrincipal = Depends(get_current_user)):
    statement = select(PublicForm).where(PublicForm.id == form_id)
    if not current_user.is_super_admin:
        statement = statement.where(PublicForm.created_by == current_user.user_id)
    form = (await db.execute(statement)).scalar_one_or_none()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    for key, value in payload.model_dump().items():
        setattr(form, key, value)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="That form slug is already in use")
    await db.refresh(form)
    return _staff_form(form)


@router.get("/{form_id}/submissions", response_model=list[FormSubmissionResponse])
async def list_submissions(form_id: uuid.UUID, db: DbSession, current_user: ResolvedPrincipal = Depends(get_current_user)):
    statement = select(PublicForm).where(PublicForm.id == form_id)
    if not current_user.is_super_admin:
        statement = statement.where(PublicForm.created_by == current_user.user_id)
    form = (await db.execute(statement)).scalar_one_or_none()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    rows = (await db.execute(select(PublicFormSubmission).options(selectinload(PublicFormSubmission.uploads)).where(PublicFormSubmission.form_id == form_id).order_by(PublicFormSubmission.created_at.desc()))).scalars().all()
    return [FormSubmissionResponse(id=str(row.id), form_id=str(form.id), created_at=row.created_at, answers=row.answers, labels=_answer_labels(form, row.answers), uploads=[{"id": str(upload.id), "field_id": upload.field_id, "name": upload.original_name, "content_type": upload.content_type, "size_bytes": upload.size_bytes} for upload in row.uploads]) for row in rows]


@router.get("/public/{slug}")
async def get_public_form(slug: str, db: DbSession):
    form = (await db.execute(select(PublicForm).where(PublicForm.slug == slug, PublicForm.is_published.is_(True)))).scalar_one_or_none()
    if not form:
        raise HTTPException(status_code=404, detail="This form is not available")
    return _public_form(form)


@router.post("/public/{slug}/submissions", status_code=status.HTTP_201_CREATED)
async def submit_public_form(slug: str, payload: FormSubmissionCreate, request: Request, db: DbSession):
    if not payload.accepted_terms:
        raise HTTPException(status_code=422, detail="You must accept the terms before submitting")
    form = (await db.execute(select(PublicForm).where(PublicForm.slug == slug, PublicForm.is_published.is_(True)))).scalar_one_or_none()
    if not form:
        raise HTTPException(status_code=404, detail="This form is not available")
    _validate_submission(form, payload.answers)
    form_id = form.id
    submission = PublicFormSubmission(form_id=form_id, answers=payload.answers, idempotency_key=payload.idempotency_key, terms_accepted_at=datetime.now(timezone.utc), ip_address=request.client.host if request.client else None, user_agent=request.headers.get("user-agent"))
    db.add(submission)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = (await db.execute(select(PublicFormSubmission).where(PublicFormSubmission.form_id == form_id, PublicFormSubmission.idempotency_key == payload.idempotency_key))).scalar_one()
        return JSONResponse(
            {"id": str(existing.id), "status": "already_submitted"},
            status_code=status.HTTP_200_OK,
        )
    return {"id": str(submission.id), "status": "submitted"}


@router.post("/public/submissions/{submission_id}/uploads", status_code=status.HTTP_201_CREATED)
async def upload_public_form_file(submission_id: uuid.UUID, field_id: str, file: UploadFile = File(...), db: DbSession = None):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", field_id):
        raise HTTPException(status_code=422, detail="Invalid field id")
    submission = (await db.execute(select(PublicFormSubmission).where(PublicFormSubmission.id == submission_id))).scalar_one_or_none()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    form = (await db.execute(select(PublicForm).where(PublicForm.id == submission.form_id))).scalar_one()
    field = _form_fields(form).get(field_id)
    if not field or field.get("type") != "file":
        raise HTTPException(status_code=422, detail="This upload does not match a file question")
    count = (await db.execute(select(PublicFormUpload).where(PublicFormUpload.submission_id == submission_id))).scalars().all()
    if len(count) >= MAX_FILES_PER_SUBMISSION:
        raise HTTPException(status_code=422, detail="A submission may contain at most five files")
    contents = await file.read(MAX_FILE_BYTES + 1)
    if len(contents) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="Each file must be 2 MB or smaller")
    if file.content_type not in ALLOWED_UPLOAD_TYPES:
        raise HTTPException(status_code=415, detail="Only PDF, JPG, PNG, and DOCX files are accepted")
    safe_name = os.path.basename(file.filename or "upload")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    storage_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}-{safe_name}")
    with open(storage_path, "wb") as stream:
        stream.write(contents)
    upload = PublicFormUpload(submission_id=submission.id, field_id=field_id, original_name=safe_name, content_type=file.content_type, storage_path=storage_path, size_bytes=len(contents), expires_at=datetime.now(timezone.utc) + timedelta(days=30))
    db.add(upload)
    await db.commit()
    return {"id": str(upload.id), "name": safe_name, "expires_at": upload.expires_at}


@router.get("/{form_id}/submissions/{submission_id}/uploads/{upload_id}")
async def download_form_upload(form_id: uuid.UUID, submission_id: uuid.UUID, upload_id: uuid.UUID, db: DbSession, current_user: ResolvedPrincipal = Depends(get_current_user)):
    statement = select(PublicForm).where(PublicForm.id == form_id)
    if not current_user.is_super_admin:
        statement = statement.where(PublicForm.created_by == current_user.user_id)
    form = (await db.execute(statement)).scalar_one_or_none()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    upload = (await db.execute(select(PublicFormUpload).join(PublicFormSubmission).where(PublicFormUpload.id == upload_id, PublicFormUpload.submission_id == submission_id, PublicFormSubmission.form_id == form.id))).scalar_one_or_none()
    if not upload or not os.path.isfile(upload.storage_path):
        raise HTTPException(status_code=404, detail="Upload not found or expired")
    return FileResponse(upload.storage_path, media_type=upload.content_type or "application/octet-stream", filename=upload.original_name)
