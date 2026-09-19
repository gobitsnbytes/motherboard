"""Deterministic OOXML form annotation and round-trip compilation.

The onboarding templates are Google Docs exports whose existing content
controls are not semantic.  This module adds stable bits&bytes content-control
tags to private document copies, updates those controls on every revision, and
repackages the resulting OOXML directory as a DOCX only at finalization.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import zipfile
from typing import Any

from lxml import etree


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}
W = f"{{{W_NS}}}"
MAX_PACKAGE_FILES = 500
MAX_UNCOMPRESSED_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True)
class Field:
    id: str
    label: str
    anchor: str
    section: str
    type: str = "text"
    required: bool = False
    editable_by: str = "participant"
    options: tuple[str, ...] = ()
    multiline: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "key": self.id,
            "label": self.label,
            "anchor": self.anchor,
            "section": self.section,
            "type": self.type,
            "required": self.required,
            "editable_by": self.editable_by,
            "options": list(self.options),
            "multiline": self.multiline,
        }


def _f(prefix: str, section: str, rows: list[tuple]) -> tuple[Field, ...]:
    fields: list[Field] = []
    for row in rows:
        key, label, anchor, *rest = row
        opts = rest[0] if rest else {}
        fields.append(Field(id=f"bnb.{prefix}.{key}", label=label, anchor=anchor, section=section, **opts))
    return tuple(fields)


FORM_FIELDS: dict[str, tuple[Field, ...]] = {
    "volunteer": (
        *_f("volunteer", "Personal information", [
            ("full_name", "Full name", "Full Name", {"required": True}),
            ("date_of_birth", "Date of birth", "Date of Birth", {"type": "date", "required": True}),
            ("gender", "Gender", "Gender"), ("phone", "Phone number", "Phone Number", {"type": "tel", "required": True}),
            ("whatsapp", "WhatsApp number", "WhatsApp Number", {"type": "tel"}),
            ("email", "Email address", "Email Address", {"type": "email", "required": True}),
            ("discord", "Discord username", "Discord Username"), ("address", "Present address", "Present Address", {"multiline": True}),
            ("city", "City / district", "City / District", {"required": True}), ("state", "State", "State", {"required": True}),
            ("pin_code", "PIN code", "PIN Code"),
        ]),
        *_f("volunteer", "Education", [
            ("institution", "School / college / institution", "Current School / College / Institution"),
            ("education", "Class / year / degree", "Class / Year / Degree"),
            ("linkedin", "LinkedIn profile", "LinkedIn Profile (if any)", {"type": "url"}),
            ("portfolio", "GitHub / portfolio", "GitHub / Portfolio (if any)", {"type": "url"}),
        ]),
        *_f("volunteer", "Contribution", [
            ("primary_track", "Primary track", "Primary Track (tick one):", {"type": "choice", "required": True, "options": ("Ops", "Outreach", "Creative", "Tech")}),
            ("secondary_track", "Secondary track", "Secondary Track (optional, tick one):", {"type": "choice", "options": ("Ops", "Outreach", "Creative", "Tech", "None")}),
            ("available_from", "Available from", "Available From (Date)", {"type": "date"}),
            ("hours_per_week", "Hours available per week", "Hours per Week Available", {"type": "number"}),
            ("preferred_days", "Preferred days", "Preferred Days:", {"type": "text"}),
            ("skills", "Relevant skills and experience", "Briefly describe your relevant skills and experience:", {"multiline": True}),
        ]),
        *_f("volunteer", "Applicant signature", [
            ("participant_signature", "Electronic signature", "Signature:", {"type": "signature", "required": True}),
            ("signed_place", "Place", "Place:", {"required": True}),
        ]),
        *_f("volunteer", "Foundation review", [
            ("assigned_role", "Assigned role / domain", "Assigned Role / Domain", {"editable_by": "hq"}),
            ("attached_team", "Attached fork / team", "Attached Fork / Team", {"editable_by": "hq"}),
            ("reporting_to", "Reporting to", "Reporting To", {"editable_by": "hq"}),
            ("effective_from", "Effective from", "Effective From", {"type": "date", "editable_by": "hq"}),
            ("hq_name", "Accepted by", "Name:", {"editable_by": "hq"}),
            ("hq_designation", "Designation", "Designation:", {"editable_by": "hq"}),
            ("hq_signature", "Foundation signature", "RECEIVED AND ACCEPTED BY GOBITSNBYTES FOUNDATION", {"type": "signature", "editable_by": "hq"}),
        ]),
    ),
    "parent_consent": (
        *_f("parent", "Minor", [
            ("minor_name", "Minor's full name", "Full Name of Minor -", {"required": True}),
            ("minor_dob", "Minor's date of birth", "Date of Birth-", {"type": "date", "required": True}),
            ("minor_gender", "Minor's gender", "Gender-"), ("minor_grade", "Class / grade / year", "Class / Grade / Year-"),
            ("minor_institution", "Institution", "Institution Name-"), ("minor_city", "City / district", "City / District-"),
            ("minor_state", "State", "State-"), ("minor_discord", "Discord username", "Discord Username-"),
        ]),
        *_f("parent", "Parent or guardian", [
            ("guardian_name", "Parent / guardian name", "Full Name of Parent / Guardian-", {"required": True}),
            ("relationship", "Relationship with minor", "Relationship with Minor-", {"required": True}),
            ("phone_primary", "Primary phone", "Phone Number (Primary)-", {"type": "tel", "required": True}),
            ("phone_secondary", "Secondary phone", "Phone Number (Secondary)-", {"type": "tel"}),
            ("guardian_email", "Email address", "Email Address-", {"type": "email", "required": True}),
            ("whatsapp", "WhatsApp number", "WhatsApp Number-", {"type": "tel"}),
            ("address", "Residential address", "Residential Address-", {"multiline": True, "required": True}),
        ]),
        *_f("parent", "Role and emergency contact", [
            ("fork_name", "Fork name", "Fork Name (if applicable)"), ("fork_location", "Fork location", "Fork Location / City"),
            ("proposed_role", "Proposed role", "Proposed Role / Capacity"), ("activities", "Activities involved", "Activities Involved", {"multiline": True}),
            ("emergency_name", "Emergency contact name", "Emergency Contact Full Name-", {"required": True}),
            ("emergency_relationship", "Emergency contact relationship", "Relationship to Minor-", {"required": True}),
            ("emergency_phone", "Emergency contact phone", "Phone (Primary)-", {"type": "tel", "required": True}),
            ("emergency_phone_secondary", "Emergency secondary phone", "Phone (Secondary / WhatsApp)-", {"type": "tel"}),
            ("emergency_email", "Emergency contact email", "Email-", {"type": "email"}),
        ]),
        *_f("parent", "Consent", [
            ("media_consent", "Photography and media consent", "Please tick all that apply:", {"type": "choice", "required": True, "options": ("Internal records only", "Internal and external use", "No photography or recording")}),
            ("guardian_signature", "Parent / guardian signature", "SIGNATURE OF PARENT / GUARDIAN", {"type": "signature", "required": True}),
            ("signed_place", "Place", "Place:", {"required": True}),
            ("minor_cosignature", "Minor co-signature (age 16+)", "CO-SIGNATURE OF MINOR", {"type": "signature"}),
        ]),
        *_f("parent", "Foundation review", [
            ("received_by", "Received by", "Received by:", {"editable_by": "hq"}),
            ("designation", "Designation", "Designation:", {"editable_by": "hq"}),
            ("volunteer_form_ref", "Volunteer form reference", "Attached to Volunteer Form Ref:", {"editable_by": "hq"}),
        ]),
    ),
    "fork_application": (
        *_f("fork.application", "Fork details", [
            ("fork_name", "Fork name", "Fork Name", {"required": True}),
            ("fork_type", "Fork type", "Fork Type (tick one):", {"type": "choice", "required": True, "options": ("City-level", "Locality-level", "Institutional", "Thematic / Digital")}),
            ("location", "Primary location", "Primary Location (City, State)", {"required": True}),
            ("institution", "Institution name", "Institution Name (if applicable)"),
            ("subdomain", "Proposed subdomain", "Proposed Subdomain (e.g. city.gobitsnbytes.org)"),
        ]),
        *_f("fork.application", "Fork lead", [
            ("lead_name", "Full name", "Full Name", {"required": True}), ("date_of_birth", "Date of birth", "Date of Birth", {"type": "date", "required": True}),
            ("phone", "Phone / WhatsApp", "Phone / WhatsApp", {"type": "tel", "required": True}),
            ("email", "Email", "Email", {"type": "email", "required": True}), ("discord", "Discord username", "Discord Username"),
            ("linkedin", "LinkedIn", "LinkedIn (personal)", {"type": "url"}), ("school", "School / college", "School / College"),
            ("address", "Address", "Address", {"multiline": True, "required": True}),
        ]),
        *_f("fork.application", "Team and setup", [
            ("team", "Initial team members and tracks", "List all team members joining the Fork at launch.", {"multiline": True, "required": True}),
            ("discord_invite", "Discord server invite", "Discord server invite (if already set up)", {"type": "url"}),
            ("community_channels", "Existing community channels", "Existing community channels (WhatsApp, Telegram, etc.)", {"multiline": True}),
            ("declarations", "Applicant declarations", "Tick all boxes before signing.", {"type": "checkbox", "required": True}),
        ]),
        *_f("fork.application", "Applicant signature", [
            ("lead_signature", "Fork lead signature", "SECTION F — APPLICANT DECLARATION", {"type": "signature", "required": True}),
            ("signed_place", "Place", "Place:", {"required": True}),
        ]),
        *_f("fork.application", "Foundation review", [
            ("application_ref", "Application reference", "Application Reference No", {"editable_by": "hq"}),
            ("received_by", "Received by", "Received by", {"editable_by": "hq"}),
            ("interviewers", "Interviewers", "Interviewer(s)", {"editable_by": "hq"}),
            ("interview_date", "Interview date", "Interview Date", {"type": "date", "editable_by": "hq"}),
            ("interview_score", "Interview score", "Interview Score", {"type": "number", "editable_by": "hq"}),
            ("board_decision", "Board decision", "Board Decision:", {"type": "choice", "editable_by": "hq", "options": ("Approved", "Conditional approval", "Deferred", "Rejected")}),
            ("board_resolution_date", "Board resolution date", "Date of Board Resolution", {"type": "date", "editable_by": "hq"}),
            ("agreement_ref", "Fork agreement reference", "Fork Agreement Ref", {"editable_by": "hq"}),
            ("certificate_no", "Recognition certificate number", "Recognition Certificate No", {"editable_by": "hq"}),
        ]),
    ),
    "fork_agreement": (
        *_f("fork.agreement", "Agreement details", [
            ("agreement_ref", "Agreement reference", "Agreement Ref:", {"editable_by": "hq", "required": True}),
            ("effective_date", "Effective date", "This Agreement is entered into on", {"type": "date", "editable_by": "hq", "required": True}),
            ("lead_name", "Fork lead full name", "Fork Lead Full Name", {"required": True}),
            ("date_of_birth", "Date of birth", "Date of Birth", {"type": "date", "required": True}),
            ("address", "Address", "Address", {"multiline": True, "required": True}), ("phone", "Phone number", "Phone Number", {"type": "tel", "required": True}),
            ("email", "Email address", "Email Address", {"type": "email", "required": True}), ("discord", "Discord username", "Discord Username"),
            ("fork_name", "Fork name", "Fork Name", {"required": True}), ("fork_location", "Fork location / city", "Fork Location / City", {"required": True}),
        ]),
        *_f("fork.agreement", "Signatures", [
            ("lead_signature", "Fork lead signature", "FORK LEAD", {"type": "signature", "required": True}),
            ("signed_place", "Place", "Place:", {"required": True}),
            ("hq_signature", "Board signature", "FOR AND ON BEHALF OF THE BOARD OF DIRECTORS", {"type": "signature", "editable_by": "hq", "required": True}),
        ]),
    ),
    "fork_certificate": (
        *_f("fork.certificate", "Recognition", [
            ("certificate_no", "Certificate number", "Certificate No", {"editable_by": "hq", "required": True}),
            ("fork_name", "Fork name", "[FORK NAME]", {"editable_by": "hq", "required": True}),
            ("lead_name", "Fork lead name", "Fork Lead Name", {"editable_by": "hq", "required": True}),
            ("location", "Location / city", "Location / City", {"editable_by": "hq", "required": True}),
            ("recognition_date", "Date of recognition", "Date of Recognition", {"type": "date", "editable_by": "hq", "required": True}),
            ("agreement_ref", "Fork agreement reference", "Issued pursuant to Fork Agreement Ref", {"editable_by": "hq", "required": True}),
            ("director_names", "Issuing directors", "FOR AND ON BEHALF OF THE BOARD OF DIRECTORS", {"editable_by": "hq", "required": True}),
            ("director_signatures", "Board signatures", "FOR AND ON BEHALF OF THE BOARD OF DIRECTORS", {"type": "signature", "editable_by": "hq", "required": True}),
        ]),
        *_f("fork.certificate", "Fork lead acknowledgement", [
            ("lead_signature", "Fork lead acknowledgement", "ACKNOWLEDGED AND ACCEPTED BY FORK LEAD", {"type": "signature", "required": True}),
            ("signed_place", "Place", "Place:", {"required": True}),
        ]),
    ),
}


def fields_for(document_key: str, *, editor: str | None = None) -> list[dict[str, Any]]:
    fields = FORM_FIELDS.get(document_key)
    if fields is None:
        raise ValueError(f"Unknown onboarding document type: {document_key}")
    if editor is not None:
        fields = tuple(field for field in fields if field.editable_by == editor)
    return [field.as_dict() for field in fields]


def template_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_member_path(root: Path, name: str) -> Path:
    pure = PurePosixPath(name)
    if pure.is_absolute() or ".." in pure.parts or not pure.parts:
        raise ValueError("Unsafe OOXML package member")
    target = (root / Path(*pure.parts)).resolve()
    if root.resolve() not in target.parents and target != root.resolve():
        raise ValueError("Unsafe OOXML package member")
    return target


def unpack_docx(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    with zipfile.ZipFile(source) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_PACKAGE_FILES or sum(item.file_size for item in infos) > MAX_UNCOMPRESSED_BYTES:
            raise ValueError("OOXML package exceeds safety limits")
        for info in infos:
            destination = _safe_member_path(target, info.filename)
            if info.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source_stream, destination.open("wb") as output:
                shutil.copyfileobj(source_stream, output)
    if not (target / "[Content_Types].xml").exists() or not (target / "word" / "document.xml").exists():
        raise ValueError("Invalid OOXML package")


def _paragraph_text(paragraph: etree._Element) -> str:
    return " ".join("".join(paragraph.xpath(".//w:t/text()", namespaces=NS)).split())


def _find_anchor(root: etree._Element, anchor: str) -> etree._Element | None:
    normalized = " ".join(anchor.split()).casefold()
    candidates = root.xpath(".//w:p", namespaces=NS)
    exact = [p for p in candidates if _paragraph_text(p).casefold() == normalized]
    if exact:
        return exact[0]
    return next((p for p in candidates if normalized in _paragraph_text(p).casefold()), None)


def _semantic_sdt(field: Field, value: Any = None) -> etree._Element:
    sdt = etree.Element(W + "sdt")
    props = etree.SubElement(sdt, W + "sdtPr")
    etree.SubElement(props, W + "alias").set(W + "val", field.label)
    etree.SubElement(props, W + "tag").set(W + "val", field.id)
    etree.SubElement(props, W + "id").set(W + "val", str(abs(hash(field.id)) % 2_000_000_000))
    content = etree.SubElement(sdt, W + "sdtContent")
    run = etree.SubElement(content, W + "r")
    text = etree.SubElement(run, W + "t")
    text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    text.text = _display_value(field, value)
    return sdt


def _display_value(field: Field, value: Any) -> str:
    if value in (None, "", []):
        return f"[Enter {field.label.lower()}]"
    if field.type == "checkbox":
        return "☒ Confirmed" if value else "☐ Not confirmed"
    if field.type == "signature":
        name = value.get("name") if isinstance(value, dict) else str(value)
        timestamp = value.get("signed_at") if isinstance(value, dict) else None
        return f"Electronically signed by {name}" + (f" on {timestamp}" if timestamp else "")
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def annotate_package(package_dir: Path, document_key: str, values: dict[str, Any] | None = None) -> list[str]:
    values = values or {}
    xml_path = package_dir / "word" / "document.xml"
    parser = etree.XMLParser(resolve_entities=False, no_network=True, remove_blank_text=False)
    tree = etree.parse(str(xml_path), parser)
    root = tree.getroot()
    existing = set(root.xpath(".//w:sdtPr/w:tag/@w:val", namespaces=NS))
    missing: list[str] = []
    for field in FORM_FIELDS[document_key]:
        controls = root.xpath(f'.//w:sdt[w:sdtPr/w:tag[@w:val="{field.id}"]]', namespaces=NS)
        if controls:
            text_nodes = controls[0].xpath(".//w:t", namespaces=NS)
            if text_nodes:
                text_nodes[0].text = _display_value(field, values.get(field.id))
            continue
        paragraph = _find_anchor(root, field.anchor)
        if paragraph is None:
            missing.append(field.id)
            continue
        tab_run = etree.Element(W + "r")
        etree.SubElement(tab_run, W + "tab")
        paragraph.append(tab_run)
        paragraph.append(_semantic_sdt(field, values.get(field.id)))
        existing.add(field.id)
    tree.write(str(xml_path), xml_declaration=True, encoding="UTF-8", standalone=True)
    return missing


def package_hash(package_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in package_dir.rglob("*") if item.is_file()):
        digest.update(path.relative_to(package_dir).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def state_hash(*, document_id: str, revision: int, previous_hash: str | None, values: dict[str, Any], package_digest: str) -> str:
    payload = {
        "document_id": document_id,
        "revision": revision,
        "previous_hash": previous_hash,
        "values": values,
        "package_hash": package_digest,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def repack_docx(package_dir: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(item for item in package_dir.rglob("*") if item.is_file()):
            archive.write(path, path.relative_to(package_dir).as_posix())
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Compiled DOCX package failed integrity validation")
    return destination


def document_blocks(template_path: Path, document_key: str) -> list[dict[str, Any]]:
    """Project a template into safe semantic blocks for the browser editor."""
    from docx import Document

    document = Document(str(template_path))
    fields = FORM_FIELDS[document_key]
    sections: list[dict[str, Any]] = []
    current = {"title": "Document", "blocks": []}
    sections.append(current)
    field_by_anchor: dict[str, list[Field]] = {}
    for field in fields:
        field_by_anchor.setdefault(field.anchor.casefold(), []).append(field)
    for paragraph in document.paragraphs:
        text = " ".join(paragraph.text.split())
        if not text:
            continue
        if text.startswith("SECTION ") or text in {"PARTIES", "SIGNATURES", "VALIDITY", "FOR AND ON BEHALF OF THE BOARD OF DIRECTORS, GOBITSNBYTES FOUNDATION", "ACKNOWLEDGED AND ACCEPTED BY FORK LEAD"}:
            current = {"title": text, "blocks": []}
            sections.append(current)
        matched = [field for anchor, candidates in field_by_anchor.items() if anchor == text.casefold() or anchor in text.casefold() for field in candidates]
        if matched:
            current["blocks"].append({"type": "fields", "text": text, "field_ids": [field.id for field in matched]})
        else:
            style = "heading" if text.startswith("SECTION ") else "legal" if len(text) > 180 else "text"
            current["blocks"].append({"type": style, "text": text})
    populated = [section for section in sections if section["blocks"]]
    for section_index, section in enumerate(populated):
        section["id"] = f"section-{section_index}"
        for block_index, block in enumerate(section["blocks"]):
            block["id"] = f"block-{section_index}-{block_index}"
    return populated


def validate_values(document_key: str, values: dict[str, Any], *, editor: str, final: bool = False) -> dict[str, str]:
    allowed = {field.id: field for field in FORM_FIELDS[document_key] if field.editable_by == editor}
    errors: dict[str, str] = {}
    for key, value in values.items():
        field = allowed.get(key)
        if field is None:
            errors[key] = "This field cannot be edited by this signer"
            continue
        if isinstance(value, str) and len(value) > (5000 if field.multiline else 500):
            errors[key] = "Value is too long"
        if field.type == "email" and value and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", str(value)):
            errors[key] = "Enter a valid email address"
        if field.type == "choice" and value and value not in field.options:
            errors[key] = "Select one of the allowed options"
    if final:
        for field in allowed.values():
            if field.required and field.type != "signature" and values.get(field.id) in (None, "", False, []):
                errors[field.id] = "This field is required"
    return errors
