"""Strict, version-pinned onboarding document materialization."""

from datetime import date, datetime, timedelta, timezone
import hashlib
import os
from pathlib import Path
import secrets
import shutil
import subprocess
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

import fitz
from lxml import etree
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import OnboardingCase, OnboardingDocument, OnboardingParticipant, SignatureAuditLog, SignatureField, SignatureRecipient, SignatureRequest


ORG_LEGAL_EMAIL = "legal@gobitsnbytes.org"


def _manifest(template: str, source_hash: str, fields: list[tuple[str, str, str]], anchors: list[dict[str, Any]]) -> dict[str, Any]:
    return {"template": template, "source_hash": source_hash, "fields": [{"key": key, "label": label, "type": field_type} for key, label, field_type in fields], "signature_anchors": anchors}


TEMPLATE_MANIFEST: dict[str, dict[str, Any]] = {
    "volunteer": _manifest("1_Volunteer_Form.docx", "e1420c8e009a04cedb25e76a0675b8f31f3ef6c393b5f2ce52206f0f8c67e854", [("full_name", "Full name", "text"), ("date_of_birth", "Date of birth", "date"), ("volunteer_role", "Volunteer role", "text"), ("track", "Track", "text"), ("consent", "Volunteer consent", "checkbox")], [{"recipient_role": "subject", "anchor": "[[signature_subject]]", "type": "signature", "required": True}, {"recipient_role": "organization", "anchor": "[[signature_organization]]", "type": "signature", "required": True}]),
    "parent_consent": _manifest("2_Parents_Consent_Fork.docx", "a6e0c10f25aadc24213bcd738fd6ea913f8d74deaf9672b409bc3bd6d387fb76", [("minor_name", "Minor name", "text"), ("parent_name", "Parent or guardian name", "text"), ("parent_email", "Parent email", "text"), ("consent", "Parent consent", "checkbox")], [{"recipient_role": "guardian", "anchor": "[[signature_guardian]]", "type": "signature", "required": True}]),
    "fork_application": _manifest("5_Fork_Application_Form.docx", "ff9113e4500c889edf688bd0620d643673730badcb669ab0d515f5e3811e2876", [("fork_name", "Fork name", "text"), ("lead_name", "Fork lead", "text"), ("summary", "Fork summary", "text")], [{"recipient_role": "lead", "anchor": "[[signature_lead]]", "type": "signature", "required": True}]),
    "fork_agreement": _manifest("4_Fork_Agreement.docx", "e7e43a74ff5decc7d0ceefd29ab065b6bebe25b7f0c35b2f467dc5394a5ae4aa", [("fork_name", "Fork name", "text"), ("lead_name", "Fork lead", "text"), ("agreement", "Agreement accepted", "checkbox")], [{"recipient_role": "lead", "anchor": "[[signature_lead]]", "type": "signature", "required": True}, {"recipient_role": "organization", "anchor": "[[signature_organization]]", "type": "signature", "required": True}]),
    "fork_certificate": _manifest("3_Fork_Recognition_Certificate.docx", "b22a28dc775615b85c2759dfdbac08df0549419e3b9c4dd09a7297238e74994c", [("fork_name", "Fork name", "text"), ("lead_name", "Fork lead", "text"), ("certificate_date", "Certificate date", "date")], [{"recipient_role": "lead", "anchor": "[[signature_lead]]", "type": "signature", "required": True}, {"recipient_role": "organization", "anchor": "[[signature_organization]]", "type": "signature", "required": True}]),
    "minor_event_consent": _manifest("6_Minor_Consent_Event.docx", "13a5616bc2396f97d358da78bcb0da5a9d15b72a13a88bf599464256928597e2", [("minor_name", "Minor name", "text"), ("parent_name", "Parent or guardian name", "text"), ("consent", "Event consent", "checkbox")], [{"recipient_role": "guardian", "anchor": "[[signature_guardian]]", "type": "signature", "required": True}]),
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


def _marker(key: str) -> str:
    return f"{{{{{key}}}}}"


def _display_value(field: dict[str, Any], value: Any) -> str:
    return "Yes" if field["type"] == "checkbox" and value is True else "No" if field["type"] == "checkbox" else "" if value is None else str(value)


def fill_template(template: Path, target: Path, manifest: dict[str, Any], values: dict[str, Any]) -> None:
    """Replace exact OOXML markers and preserve all existing document structure."""
    if hashlib.sha256(template.read_bytes()).hexdigest() != manifest["source_hash"]:
        raise RuntimeError("Onboarding template hash does not match its registered version")
    replacements = {_marker(field["key"]): _display_value(field, values.get(field["key"])) for field in manifest["fields"]}
    counts = {marker: 0 for marker in replacements}
    with ZipFile(template) as source, ZipFile(target, "w", ZIP_DEFLATED) as output:
        for member in source.infolist():
            payload = source.read(member.filename)
            if member.filename.startswith("word/") and member.filename.endswith(".xml"):
                root = etree.fromstring(payload)
                for node in root.xpath(".//w:t", namespaces={"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}):
                    value = node.text or ""
                    for marker, replacement in replacements.items():
                        counts[marker] += value.count(marker)
                        value = value.replace(marker, replacement)
                    node.text = value
                payload = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
            output.writestr(member, payload)
    invalid = [marker for marker, count in counts.items() if count != 1]
    if invalid:
        target.unlink(missing_ok=True)
        raise RuntimeError(f"Onboarding template marker contract failed: {', '.join(invalid)}")


def render_docx_to_pdf(docx_path: Path, output_dir: Path) -> Path:
    soffice = os.getenv("ONBOARDING_SOFFICE_PATH") or shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise RuntimeError("LibreOffice Writer is required to render onboarding DOCX files")
    result = subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(output_dir), str(docx_path)], capture_output=True, text=True, timeout=90, check=False)
    pdf_path = output_dir / f"{docx_path.stem}.pdf"
    if result.returncode != 0 or not pdf_path.is_file():
        raise RuntimeError("Onboarding DOCX rendering failed")
    return pdf_path


async def create_signature_request(db: AsyncSession, *, case: OnboardingCase, document: OnboardingDocument, pdf_path: Path, signer_specs: list[dict[str, Any]], values: dict[str, Any], include_legal: bool = True) -> SignatureRequest:
    request = SignatureRequest(title=f"{case.title} - {document.document_key.replace('_', ' ').title()}", status="pending", original_file_path=str(pdf_path), created_by=case.created_by, expires_at=datetime.now(timezone.utc) + timedelta(days=30))
    db.add(request)
    await db.flush()
    recipients: dict[str, SignatureRecipient] = {}
    for order, spec in enumerate(signer_specs, start=1):
        recipient = SignatureRecipient(request_id=request.id, name=spec["name"], email=spec["email"], role=spec.get("role", "subject"), signing_order=order, status="pending", access_token=secrets.token_urlsafe(24), requires_otp=True, allowed_sig_type=spec.get("allowed_sig_type", "any"))
        db.add(recipient); await db.flush(); recipients[recipient.role] = recipient
    if include_legal:
        legal = SignatureRecipient(request_id=request.id, name="GOBITSNBYTES FOUNDATION - Legal", email=ORG_LEGAL_EMAIL, role="organization", signing_order=99, status="pending", access_token=secrets.token_urlsafe(24), requires_otp=True, allowed_sig_type="email_only")
        db.add(legal); await db.flush(); recipients[legal.role] = legal
    with fitz.open(str(pdf_path)) as pdf_doc:
        for anchor in manifest_for(document.document_key)["signature_anchors"]:
            recipient = recipients.get(anchor["recipient_role"])
            matches = [(number, rect) for number, page in enumerate(pdf_doc, start=1) for rect in page.search_for(anchor["anchor"])]
            if recipient is None or len(matches) != 1:
                raise RuntimeError(f"Onboarding signature anchor contract failed: {anchor['anchor']}")
            page_number, rect = matches[0]; page = pdf_doc[page_number - 1]
            db.add(SignatureField(request_id=request.id, recipient_id=recipient.id, type=anchor["type"], page_number=page_number, pos_x=100 * rect.x0 / page.rect.width, pos_y=100 * rect.y0 / page.rect.height, width=100 * rect.width / page.rect.width, height=100 * rect.height / page.rect.height, required=anchor["required"]))
    db.add(SignatureAuditLog(request_id=request.id, action="created", ip_address="onboarding", user_agent="motherboard", details=f"Created from onboarding case {case.id}"))
    return request


async def materialize_document(db: AsyncSession, *, case: OnboardingCase, document: OnboardingDocument, participant: OnboardingParticipant, values: dict[str, Any]) -> SignatureRequest:
    manifest = manifest_for(document.document_key); template = template_root() / manifest["template"]
    if not template.is_file():
        raise FileNotFoundError(f"Onboarding template is missing: {manifest['template']}")
    folder = storage_root() / str(case.id) / str(document.id); folder.mkdir(parents=True, exist_ok=True)
    source_path = folder / manifest["template"]; filled_path = folder / f"filled_{manifest['template']}"
    shutil.copyfile(template, source_path); fill_template(source_path, filled_path, manifest, values)
    pdf_path = render_docx_to_pdf(filled_path, folder)
    document.source_docx_path = str(source_path); document.filled_docx_path = str(filled_path); document.source_pdf_path = str(pdf_path)
    document.evidence_hash = hashlib.sha256(filled_path.read_bytes()).hexdigest(); document.field_values = values; document.status = "awaiting_signatures"
    signer_role = "guardian" if participant.role == "parent" else "lead" if document.document_key.startswith("fork_") else "subject"
    request = await create_signature_request(db, case=case, document=document, pdf_path=pdf_path, signer_specs=[{"name": participant.name, "email": participant.email, "role": signer_role}], values=values)
    document.signature_request_id = request.id
    return request
