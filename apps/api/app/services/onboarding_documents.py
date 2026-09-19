"""Strict, version-pinned onboarding document materialization."""

from datetime import date, datetime, timedelta, timezone
import hashlib
import os
from pathlib import Path
import secrets
import shutil
import subprocess
from typing import Any

import fitz
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import OnboardingCase, OnboardingDocument, SignatureAuditLog, SignatureField, SignatureRecipient, SignatureRequest
from app.services.semantic_ooxml import fields_for, signature_markers


def _manifest(template: str, source_hash: str, fields: list[tuple[str, str, str]]) -> dict[str, Any]:
    return {"template": template, "source_hash": source_hash, "fields": [{"key": key, "label": label, "type": field_type} for key, label, field_type in fields]}


TEMPLATE_MANIFEST: dict[str, dict[str, Any]] = {
    "volunteer": _manifest("1_Volunteer_Form.docx", "e1420c8e009a04cedb25e76a0675b8f31f3ef6c393b5f2ce52206f0f8c67e854", [("full_name", "Full name", "text"), ("date_of_birth", "Date of birth", "date"), ("volunteer_role", "Volunteer role", "text"), ("track", "Track", "text"), ("consent", "Volunteer consent", "checkbox")]),
    "parent_consent": _manifest("2_Parents_Consent_Fork.docx", "a6e0c10f25aadc24213bcd738fd6ea913f8d74deaf9672b409bc3bd6d387fb76", [("minor_name", "Minor name", "text"), ("parent_name", "Parent or guardian name", "text"), ("parent_email", "Parent email", "text"), ("consent", "Parent consent", "checkbox")]),
    "fork_application": _manifest("5_Fork_Application_Form.docx", "ff9113e4500c889edf688bd0620d643673730badcb669ab0d515f5e3811e2876", [("fork_name", "Fork name", "text"), ("lead_name", "Fork lead", "text"), ("summary", "Fork summary", "text")]),
    "fork_agreement": _manifest("4_Fork_Agreement.docx", "e7e43a74ff5decc7d0ceefd29ab065b6bebe25b7f0c35b2f467dc5394a5ae4aa", [("fork_name", "Fork name", "text"), ("lead_name", "Fork lead", "text"), ("agreement", "Agreement accepted", "checkbox")]),
    "fork_certificate": _manifest("3_Fork_Recognition_Certificate.docx", "b22a28dc775615b85c2759dfdbac08df0549419e3b9c4dd09a7297238e74994c", [("fork_name", "Fork name", "text"), ("lead_name", "Fork lead", "text"), ("certificate_date", "Certificate date", "date")]),
    "minor_event_consent": _manifest("6_Minor_Consent_Event.docx", "13a5616bc2396f97d358da78bcb0da5a9d15b72a13a88bf599464256928597e2", [("minor_name", "Minor name", "text"), ("parent_name", "Parent or guardian name", "text"), ("consent", "Event consent", "checkbox")]),
}


def age_on(date_of_birth: str, today: date | None = None) -> int:
    born = date.fromisoformat(date_of_birth)
    today = today or datetime.now(timezone.utc).date()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def validate_age(date_of_birth: str, today: date | None = None) -> tuple[int, bool]:
    age = age_on(date_of_birth, today=today)
    if age < 13:
        raise ValueError("Participants must be at least 13 years old for this workflow")
    return age, age < 18


def hash_portal_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_portal_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    return token, hash_portal_token(token)


def template_root() -> Path:
    return Path(os.getenv("ONBOARDING_TEMPLATES_DIR", str(Path(__file__).resolve().parents[2] / "templates")))


def storage_root() -> Path:
    root = Path(os.getenv("ONBOARDING_STORAGE_DIR", str(Path.cwd() / "data" / "onboarding")))
    root.mkdir(parents=True, exist_ok=True)
    return root


def manifest_for(document_key: str) -> dict[str, Any]:
    try:
        return TEMPLATE_MANIFEST[document_key]
    except KeyError as exc:
        raise ValueError(f"Unknown onboarding document type: {document_key}") from exc


def render_docx_to_pdf(docx_path: Path, output_dir: Path) -> Path:
    soffice = os.getenv("ONBOARDING_SOFFICE_PATH") or shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise RuntimeError("LibreOffice Writer is required to render onboarding DOCX files")
    result = subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(output_dir), str(docx_path)], capture_output=True, text=True, timeout=90, check=False)
    pdf_path = output_dir / f"{docx_path.stem}.pdf"
    if result.returncode != 0 or not pdf_path.is_file():
        raise RuntimeError("Onboarding DOCX rendering failed")
    return pdf_path


async def create_signature_request(db: AsyncSession, *, case: OnboardingCase, document: OnboardingDocument, pdf_path: Path, signer_specs: list[dict[str, Any]]) -> SignatureRequest:
    request = SignatureRequest(title=f"{case.title} - {document.document_key.replace('_', ' ').title()}", status="pending", original_file_path=str(pdf_path), created_by=case.created_by, expires_at=datetime.now(timezone.utc) + timedelta(days=30))
    db.add(request)
    await db.flush()
    recipients: dict[str, SignatureRecipient] = {}
    for order, spec in enumerate(signer_specs, start=1):
        recipient = SignatureRecipient(request_id=request.id, name=spec["name"], email=spec["email"], role=spec.get("role", "subject"), signing_order=order, status="pending", access_token=secrets.token_urlsafe(24), requires_otp=True, allowed_sig_type=spec.get("allowed_sig_type", "any"))
        db.add(recipient)
        await db.flush()
        recipients[recipient.role] = recipient
    organization = recipients.get("organization")
    signer = next((recipient for role, recipient in recipients.items() if role != "organization"), None)
    markers = signature_markers(document.document_key)
    with fitz.open(str(pdf_path)) as pdf_doc:
        for field in fields_for(document.document_key):
            if field["type"] != "signature":
                continue
            recipient = organization if field["editable_by"] == "hq" else signer
            marker = markers[field["id"]]
            matches = [(number, rect) for number, page in enumerate(pdf_doc, start=1) for rect in page.search_for(marker)]
            if recipient is None or len(matches) != 1:
                raise RuntimeError(f"Onboarding signature anchor contract failed: {field['label']} ({len(matches)} placeholders found in the rendered PDF)")
            page_number, rect = matches[0]
            page = pdf_doc[page_number - 1]
            db.add(SignatureField(request_id=request.id, recipient_id=recipient.id, type="signature", page_number=page_number, pos_x=100 * rect.x0 / page.rect.width, pos_y=100 * rect.y0 / page.rect.height, width=100 * rect.width / page.rect.width, height=100 * rect.height / page.rect.height, required=field["required"]))
    db.add(SignatureAuditLog(request_id=request.id, action="created", ip_address="onboarding", user_agent="motherboard", details=f"Created from onboarding case {case.id}"))
    return request
