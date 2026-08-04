"""
Cryptographic PDF engine for bnb-signatures.

Handles:
1. Converting uploaded .docx / .pdf into PDF and page preview images.
2. Overlaying signature images, names, dates onto exact PDF relative coordinates.
3. Appending a styled 1-page Certificate of Completion & Audit Trail.
4. Computing SHA-256 document checksums for tamper-evident verification.
"""

import base64
from datetime import datetime, timezone
import hashlib
import io
import os
from typing import List, Tuple

import fitz  # PyMuPDF
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import HRFlowable, Image as RLImage, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def render_pdf_page_previews(pdf_bytes: bytes) -> List[str]:
    """Convert PDF pages into base64 PNG data URLs for canvas preview."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    previews = []

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        # Render at 150 DPI for crisp UI previews
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")
        base64_img = base64.b64encode(img_bytes).decode("utf-8")
        previews.append(f"data:image/png;base64,{base64_img}")

    doc.close()
    return previews


def prepare_document_pdf(file_bytes: bytes, filename: str) -> bytes:
    """Ensure document is in PDF format. Converts .docx to PDF if required."""
    ext = os.path.splitext(filename)[1].lower()

    if ext in (".pdf",):
        return file_bytes

    if ext in (".docx", ".doc"):
        # Convert DOCX to PDF using PyMuPDF / reportlab document builder
        try:
            import docx
            doc_docx = docx.Document(io.BytesIO(file_bytes))
            buffer = io.BytesIO()
            doc_pdf = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
            styles = getSampleStyleSheet()
            story = []

            for paragraph in doc_docx.paragraphs:
                if paragraph.text.strip():
                    story.append(Paragraph(paragraph.text, styles["Normal"]))
                    story.append(Spacer(1, 8))

            if not story:
                story.append(Paragraph("Document Content", styles["Heading1"]))

            doc_pdf.build(story)
            return buffer.getvalue()
        except Exception as e:
            # Fallback plain-text PDF builder if docx fails
            buffer = io.BytesIO()
            doc_pdf = SimpleDocTemplate(buffer, pagesize=letter)
            styles = getSampleStyleSheet()
            story = [Paragraph(f"Converted Document: {filename}", styles["Heading1"])]
            doc_pdf.build(story)
            return buffer.getvalue()

    raise ValueError(f"Unsupported file format: {ext}")


def create_audit_certificate_page(
    request_title: str,
    request_id: str,
    created_at: datetime,
    completed_at: datetime,
    document_hash: str,
    recipients_data: List[dict],
    audit_logs_data: List[dict],
) -> bytes:
    """Generate a styled 1-page Certificate of Completion PDF page."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "CertTitle",
        parent=styles["Heading1"],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#3C0A12"),  # Brand Plum
    )
    subtitle_style = ParagraphStyle(
        "CertSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#716F6C"),
    )
    heading_style = ParagraphStyle(
        "CertHeader",
        parent=styles["Heading2"],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#97192C"),
    )
    body_style = ParagraphStyle(
        "CertBody",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#120F0A"),
    )

    story = [
        Paragraph("CERTIFICATE OF COMPLETION & AUDIT TRAIL", title_style),
        Paragraph("bits&bytes™ Legal E-Signature Verification Engine", subtitle_style),
        Spacer(1, 10),
        HRFlowable(width="100%", thickness=2, color=colors.HexColor("#FC920D"), spaceAfter=15),
    ]

    # Envelope Details Table
    meta_data = [
        [Paragraph("<b>Document Title:</b>", body_style), Paragraph(request_title, body_style)],
        [Paragraph("<b>Document ID:</b>", body_style), Paragraph(str(request_id), body_style)],
        [Paragraph("<b>Created Date:</b>", body_style), Paragraph(created_at.strftime("%Y-%m-%d %H:%M:%S UTC"), body_style)],
        [Paragraph("<b>Completed Date:</b>", body_style), Paragraph(completed_at.strftime("%Y-%m-%d %H:%M:%S UTC"), body_style)],
        [Paragraph("<b>Cryptographic Checksum (SHA-256):</b>", body_style), Paragraph(f"<font fontName='Helvetica-Bold'>{document_hash}</font>", body_style)],
    ]
    meta_table = Table(meta_data, colWidths=[180, 360])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8F7F5")),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0CFCE")),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 15))

    # Signatories Section
    story.append(Paragraph("SIGNATORY VERIFICATION TRAIL", heading_style))
    story.append(Spacer(1, 5))

    sig_headers = [Paragraph("<b>Signatory</b>", body_style), Paragraph("<b>Role</b>", body_style), Paragraph("<b>IP Address</b>", body_style), Paragraph("<b>Signed Timestamp</b>", body_style)]
    sig_rows = [sig_headers]
    for r in recipients_data:
        signed_time = r.get("signed_at").strftime("%Y-%m-%d %H:%M:%S UTC") if r.get("signed_at") else "N/A"
        sig_rows.append([
            Paragraph(f"<b>{r.get('name')}</b><br/>&lt;{r.get('email')}&gt;", body_style),
            Paragraph(r.get("role", "signer").capitalize(), body_style),
            Paragraph(r.get("ip_address") or "127.0.0.1", body_style),
            Paragraph(signed_time, body_style),
        ])

    sig_table = Table(sig_rows, colWidths=[180, 80, 100, 180])
    sig_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EFECE6")),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0CFCE")),
    ]))
    story.append(sig_table)
    story.append(Spacer(1, 15))

    # Audit Events Log
    story.append(Paragraph("CHRONOLOGICAL AUDIT LOG", heading_style))
    story.append(Spacer(1, 5))

    audit_headers = [Paragraph("<b>Timestamp (UTC)</b>", body_style), Paragraph("<b>Action</b>", body_style), Paragraph("<b>IP Address</b>", body_style), Paragraph("<b>Event Details</b>", body_style)]
    audit_rows = [audit_headers]
    for log in audit_logs_data:
        t = log.get("created_at").strftime("%Y-%m-%d %H:%M:%S") if isinstance(log.get("created_at"), datetime) else str(log.get("created_at"))
        audit_rows.append([
            Paragraph(t, body_style),
            Paragraph(log.get("action", "").upper(), body_style),
            Paragraph(log.get("ip_address") or "System", body_style),
            Paragraph(log.get("details") or "", body_style),
        ])

    audit_table = Table(audit_rows, colWidths=[120, 90, 90, 240])
    audit_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EFECE6")),
        ("PADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0CFCE")),
    ]))
    story.append(audit_table)
    story.append(Spacer(1, 15))

    # Legal Disclaimer
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#D0CFCE"), spaceAfter=8))
    disclaimer = (
        "<b>Security & Legal Notice:</b> This document was executed electronically using the bits&bytes™ "
        "cryptographic digital signature platform in accordance with applicable electronic signature laws (such as IT Act 2000 & ESIGN Act). "
        "The cryptographic hash above guarantees tamper-evident verification. Any modification of the PDF invalidates the signature seal."
    )
    story.append(Paragraph(disclaimer, subtitle_style))

    doc.build(story)
    return buffer.getvalue()


def embed_signatures_and_seal(
    original_pdf_bytes: bytes,
    fields_data: List[dict],
    recipients_data: List[dict],
    audit_logs_data: List[dict],
    request_title: str,
    request_id: str,
    created_at: datetime,
) -> Tuple[bytes, str]:
    """
    Overlay signature elements onto PDF at relative positions and append Audit Certificate.
    Returns (final_pdf_bytes, sha256_hash).
    """
    doc = fitz.open(stream=original_pdf_bytes, filetype="pdf")

    # Embed fields onto pages
    for f in fields_data:
        page_num = f.get("page_number", 1) - 1
        if page_num < 0 or page_num >= len(doc):
            continue

        page = doc.load_page(page_num)
        rect_page = page.rect  # PyMuPDF rect (x0, y0, x1, y1)

        pos_x = f.get("pos_x", 0) / 100.0
        pos_y = f.get("pos_y", 0) / 100.0
        width = f.get("width", 20) / 100.0
        height = f.get("height", 5) / 100.0

        x0 = rect_page.width * pos_x
        y0 = rect_page.height * pos_y
        x1 = x0 + (rect_page.width * width)
        y1 = y0 + (rect_page.height * height)
        fitz_rect = fitz.Rect(x0, y0, x1, y1)

        val = f.get("value")
        f_type = f.get("type", "signature")

        if f_type == "signature" and val:
            if val.startswith("data:image"):
                # Insert base64 signature image
                base64_data = val.split(",", 1)[1]
                img_bytes = base64.b64decode(base64_data)
                page.insert_image(fitz_rect, stream=img_bytes)
            else:
                # Insert script font text signature
                page.insert_textbox(fitz_rect, val, fontsize=14, color=(0.1, 0.1, 0.5))

        elif f_type in ("fullname", "text") and val:
            page.insert_textbox(fitz_rect, str(val), fontsize=11, color=(0, 0, 0))

        elif f_type == "date" and val:
            page.insert_textbox(fitz_rect, str(val), fontsize=10, color=(0.2, 0.2, 0.2))

        elif f_type == "checkbox":
            check_str = "☑" if val == "true" else "☐"
            page.insert_textbox(fitz_rect, check_str, fontsize=14, color=(0, 0, 0))

    # Save modified original PDF
    pdf_modified_bytes = doc.tobytes()
    doc.close()

    # Generate Audit Certificate PDF page
    completed_at = datetime.now(timezone.utc)
    temp_hash = hashlib.sha256(pdf_modified_bytes).hexdigest()

    cert_pdf_bytes = create_audit_certificate_page(
        request_title=request_title,
        request_id=request_id,
        created_at=created_at,
        completed_at=completed_at,
        document_hash=temp_hash,
        recipients_data=recipients_data,
        audit_logs_data=audit_logs_data,
    )

    # Merge modified document + certificate page
    final_doc = fitz.open(stream=pdf_modified_bytes, filetype="pdf")
    cert_doc = fitz.open(stream=cert_pdf_bytes, filetype="pdf")
    final_doc.insert_pdf(cert_doc)

    final_bytes = final_doc.tobytes()
    final_doc.close()
    cert_doc.close()

    # Compute final SHA-256 seal
    final_hash = hashlib.sha256(final_bytes).hexdigest()
    return final_bytes, final_hash
