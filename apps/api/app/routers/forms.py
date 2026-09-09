"""Staff form builder and anonymous public form submission endpoints."""
from datetime import datetime, timedelta, timezone
import os
import re
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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


@router.get("", response_model=list[dict])
async def list_forms(db: DbSession, current_user: ResolvedPrincipal = Depends(get_current_user)):
    rows = (await db.execute(select(PublicForm).where(PublicForm.created_by == current_user.user_id).order_by(PublicForm.updated_at.desc()))).scalars().all()
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
    form = (await db.execute(select(PublicForm).where(PublicForm.id == form_id, PublicForm.created_by == current_user.user_id))).scalar_one_or_none()
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
    form = (await db.execute(select(PublicForm).where(PublicForm.id == form_id, PublicForm.created_by == current_user.user_id))).scalar_one_or_none()
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    rows = (await db.execute(select(PublicFormSubmission).where(PublicFormSubmission.form_id == form_id).order_by(PublicFormSubmission.created_at.desc()))).scalars().all()
    return [FormSubmissionResponse(id=str(row.id), created_at=row.created_at, answers=row.answers) for row in rows]


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
    submission = PublicFormSubmission(form_id=form.id, answers=payload.answers, idempotency_key=payload.idempotency_key, terms_accepted_at=datetime.now(timezone.utc), ip_address=request.client.host if request.client else None, user_agent=request.headers.get("user-agent"))
    db.add(submission)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = (await db.execute(select(PublicFormSubmission).where(PublicFormSubmission.form_id == form.id, PublicFormSubmission.idempotency_key == payload.idempotency_key))).scalar_one()
        return {"id": str(existing.id), "status": "already_submitted"}
    return {"id": str(submission.id), "status": "submitted"}


@router.post("/public/submissions/{submission_id}/uploads", status_code=status.HTTP_201_CREATED)
async def upload_public_form_file(submission_id: uuid.UUID, field_id: str, file: UploadFile = File(...), db: DbSession = None):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", field_id):
        raise HTTPException(status_code=422, detail="Invalid field id")
    submission = (await db.execute(select(PublicFormSubmission).where(PublicFormSubmission.id == submission_id))).scalar_one_or_none()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
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
