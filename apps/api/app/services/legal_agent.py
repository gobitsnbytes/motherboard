"""
Legal Agent service (Dottr-style email-native contract teammate).

Watches the legal inbox over IMAPS, ingests attached contracts through the
Contract Assistant analysis pipeline (shared code path with /analyze), replies
from legal@gobitsnbytes.org with a plain-language risk summary, and nudges
pending signatories on a 3/7/14-day cadence.

Storage constraints honoured (no schema changes):
- Inbound dedupe uses the dedicated unique ``ca_contracts.message_id`` column,
  with a portable Python-side fallback scan over recent ``ca_events.payload``
  JSON blobs (message ids recorded there too).
- Nudge state lives in ``ca_events`` (type ``signature_reminder_sent``,
  payload carries recipient_id + cadence_day) and IAM audit entries
  (action ``signature.reminder_sent``).
"""

import asyncio
import email
import email.utils
import html
import imaplib
import logging
import os
import random
import re
import smtplib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import decode_header, make_header
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings, get_settings
from app.db.models import (
    ContractAssistantContract,
    ContractAssistantEnvelope,
    ContractAssistantEvent,
    SignatureAuditLog,
    SignatureRequest,
)

logger = logging.getLogger("app.services.legal_agent")

NUDGE_CADENCE_DAYS = [3, 7, 14]
MAX_NUDGES_PER_RECIPIENT = 3
REMINDER_EVENT_TYPE = "signature_reminder_sent"
INBOUND_EVENT_TYPE = "inbound_email_ingested"
_MAX_MESSAGES_PER_POLL = 50
_MAX_ATTACHMENTS_PER_MESSAGE = 5
_MAX_DEDUPE_SCAN = 500

_SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}

_CONTRACT_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
}
_CONTRACT_EXTENSIONS = (".pdf", ".docx", ".doc")

_last_poll_at: Optional[datetime] = None


def get_last_poll_at() -> Optional[datetime]:
    """Timestamp of the last completed inbox poll (module-lifetime cache)."""
    return _last_poll_at


# ---------------------------------------------------------------------------
# Message parsing (stdlib only)
# ---------------------------------------------------------------------------

@dataclass
class LegalInboxMessage:
    message_id: Optional[str]
    in_reply_to: Optional[str]
    references: Optional[str]
    from_addr: str
    subject: str
    body_text: str
    attachments: List[Tuple[str, str, bytes]] = field(default_factory=list)
    received_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_automated: bool = False


def _decode_mime_header(value: Optional[str]) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def _is_contract_attachment(filename: str, content_type: str) -> bool:
    ct = (content_type or "").lower().strip()
    ext = os.path.splitext(filename or "")[1].lower()
    if ct in _CONTRACT_CONTENT_TYPES:
        return True
    if ct == "application/octet-stream" and ext in _CONTRACT_EXTENSIONS:
        return True
    return False


def parse_message(raw_bytes: bytes) -> LegalInboxMessage:
    """Parse an RFC822 payload into a :class:`LegalInboxMessage`.

    Walks multipart trees, decodes the first text/plain body, extracts
    contract-document attachments (pdf/docx/doc), and detects automated
    bounces or mailing-list headers.
    """
    msg = email.message_from_bytes(raw_bytes)

    from_addr = email.utils.parseaddr(_decode_mime_header(msg.get("From", "")))[1]
    subject = _decode_mime_header(msg.get("Subject", ""))

    try:
        received_at = email.utils.parsedate_to_datetime(msg.get("Date"))
    except (TypeError, ValueError):
        received_at = datetime.now(timezone.utc)
    if received_at is None:
        received_at = datetime.now(timezone.utc)
    if received_at.tzinfo is None:
        received_at = received_at.replace(tzinfo=timezone.utc)

    # Detect automated bounces, system notifications, and auto-responders
    auto_submitted = (msg.get("Auto-Submitted") or "").strip().lower()
    precedence = (msg.get("Precedence") or "").strip().lower()
    x_autoreply = (msg.get("X-Autoreply") or msg.get("X-Autorespond") or "").strip().lower()
    return_path = (msg.get("Return-Path") or "").strip()
    content_type_raw = (msg.get("Content-Type") or "").lower()

    is_automated = False
    if auto_submitted and auto_submitted not in ("no", ""):
        is_automated = True
    elif precedence in ("bulk", "junk", "list", "auto_reply"):
        is_automated = True
    elif x_autoreply:
        is_automated = True
    elif return_path in ("<>", "<MAILER-DAEMON>"):
        is_automated = True
    elif "report-type=delivery-status" in content_type_raw or msg.get_content_type() == "multipart/report":
        is_automated = True
    elif any(subject.lower().startswith(p) for p in (
        "undelivered mail", "delivery status notification", "failure notice", "returned mail", "mail delivery failed", "out of office"
    )):
        is_automated = True

    body_text = ""
    plain_parts: List[str] = []
    html_parts: List[str] = []
    attachments: List[Tuple[str, str, bytes]] = []

    for part in msg.walk():
        if part.is_multipart():
            continue
        content_type = part.get_content_type()
        filename = _decode_mime_header(part.get_filename())
        disposition = (part.get("Content-Disposition") or "").lower()

        if not filename and "attachment" not in disposition:
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    plain_parts.append(payload.decode(charset, errors="replace"))
                continue
            elif content_type == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    html_parts.append(payload.decode(charset, errors="replace"))
                continue

        if filename or "attachment" in disposition:
            payload = part.get_payload(decode=True) or b""
            if _is_contract_attachment(filename, content_type):
                attachments.append((filename or "attachment.pdf", content_type, payload))

    body_text = _extract_clean_email_body(plain_parts, html_parts)

    return LegalInboxMessage(
        message_id=msg.get("Message-ID"),
        in_reply_to=msg.get("In-Reply-To"),
        references=msg.get("References"),
        from_addr=from_addr,
        subject=subject,
        body_text=body_text,
        attachments=attachments[:_MAX_ATTACHMENTS_PER_MESSAGE],
        received_at=received_at,
        is_automated=is_automated,
    )


def _extract_clean_email_body(plain_parts: List[str], html_parts: List[str]) -> str:
    """Extract clean question text, falling back to HTML if plain text is absent.

    Strips email client reply quotes (e.g. Gmail blockquotes, attribution lines)
    and signatures so the retrieval query focuses solely on the user's question.
    """
    raw_text = ""
    is_html = False

    combined_plain = "\n".join(p for p in plain_parts if p.strip()).strip()
    if combined_plain:
        raw_text = combined_plain
        is_html = False
    elif html_parts:
        raw_text = "\n".join(h for h in html_parts if h.strip()).strip()
        is_html = True

    if not raw_text:
        return ""

    if is_html:
        # Strip script / style / head tags
        raw_text = re.sub(r"<(?:script|style|head)[^>]*>[\s\S]*?</(?:script|style|head)>", "", raw_text, flags=re.IGNORECASE)
        # Strip quoted reply containers and smartmail signatures
        raw_text = re.sub(r'<div[^>]*class=[\'"](?:gmail_quote|gmail_extra)[\'"][\s\S]*', "", raw_text, flags=re.IGNORECASE)
        raw_text = re.sub(r'<blockquote[\s\S]*?</blockquote>', "", raw_text, flags=re.IGNORECASE)
        raw_text = re.sub(r'<div[^>]*data-smartmail=[\'"]gmail_signature[\'"][\s\S]*?</div>', "", raw_text, flags=re.IGNORECASE)
        raw_text = re.sub(r'<div[^>]*id=[\'"](?:appendonsend|divRplyFwdMsg)[\'"][\s\S]*', "", raw_text, flags=re.IGNORECASE)
        # Convert break and block tags to newlines
        raw_text = re.sub(r"<(?:br|/p|/div|/tr|/li)[^>]*>", "\n", raw_text, flags=re.IGNORECASE)
        # Strip all other HTML tags
        raw_text = re.sub(r"<[^>]+>", " ", raw_text)
        raw_text = html.unescape(raw_text)

    # Clean reply quote headers and delimiters in text
    lines = []
    for line in raw_text.splitlines():
        trimmed = line.strip()
        # Cut off email reply quote headers
        if re.match(r"^On\s+.*,\s+.*wrote:\s*$", trimmed, flags=re.IGNORECASE):
            break
        if re.match(r"^-+\s*Original Message\s*-+", trimmed, flags=re.IGNORECASE):
            break
        if trimmed.startswith(">"):
            continue
        # Stop at standard signature delimiter
        if trimmed in ("--", "-- ", "___"):
            break
        lines.append(trimmed)

    return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# Inbound ingestion
# ---------------------------------------------------------------------------

async def is_duplicate_inbound(db: AsyncSession, message_id: Optional[str]) -> bool:
    """True when this Message-ID was already ingested.

    Primary check hits the indexed ``ca_contracts.message_id`` column; the
    fallback scans up to 500 recent ``ca_events`` payloads in Python so the
    check stays portable across SQLite/Postgres JSON dialects.
    """
    if not message_id:
        return False

    stmt = (
        select(ContractAssistantContract.id)
        .where(ContractAssistantContract.message_id == message_id)
        .limit(1)
    )
    res = await db.execute(stmt)
    if res.scalar_one_or_none() is not None:
        return True

    evt_stmt = (
        select(ContractAssistantEvent.payload)
        .where(ContractAssistantEvent.type == INBOUND_EVENT_TYPE)
        .order_by(ContractAssistantEvent.created_at.desc())
        .limit(_MAX_DEDUPE_SCAN)
    )
    evt_res = await db.execute(evt_stmt)
    for payload in evt_res.scalars():
        if isinstance(payload, dict) and payload.get("message_id") == message_id:
            return True
    return False


async def handle_inbox_message(
    db: AsyncSession,
    settings: Settings,
    message: LegalInboxMessage,
) -> bool:
    """Ingest contract attachments from one inbound message and reply.

    Returns True when the message can be marked as seen (deduped, handled, or
    intentionally ignored because it carried no contract documents).
    """
    # Imported here so both entry points share one analysis implementation
    # without creating an import cycle at module load.
    from app.routers.contract_assistant import analyze_contract_bytes

    sender_lower = (message.from_addr or "").strip().lower()
    org_mailbox_lower = (settings.legal_org_mailbox or "legal@gobitsnbytes.org").strip().lower()

    # Never process or reply to messages sent by this mailbox (prevents ping-pong loop)
    if not sender_lower or sender_lower == org_mailbox_lower or sender_lower == "legal@gobitsnbytes.org":
        logger.info("[LegalAgent] Dropping self-addressed message (%s)", sender_lower)
        return True

    # Drop automated bounces, system notifications, mailer-daemon, and marketing relays
    if (
        message.is_automated
        or any(sender_lower.startswith(p) for p in ("mailer-daemon@", "postmaster@", "noreply@", "no-reply@", "bounces-", "bounce@"))
        or any(d in sender_lower for d in ("sender-sib.com", "sendinblue.com"))
    ):
        logger.info("[LegalAgent] Dropping automated/bounce message from %s (subject: %s)", sender_lower, message.subject)
        return True

    subject_lower = (message.subject or "").strip().lower()
    if any(subject_lower.startswith(p) for p in (
        "undelivered mail", "delivery status notification", "failure notice", "returned mail", "mail delivery failed"
    )):
        logger.info("[LegalAgent] Dropping delivery failure notification: %s", message.subject)
        return True

    if await is_duplicate_inbound(db, message.message_id):
        logger.info("[LegalAgent] Skipping duplicate Message-ID %s", message.message_id)
        return True

    if not message.attachments:
        if not sender_lower.endswith("@gobitsnbytes.org"):
            await _send_policy_reply(
                settings, message,
                "This mailbox can review attached PDF or DOCX agreements. Policy guidance is available to verified @gobitsnbytes.org team members.",
                sources=[],
            )
            return True

        from app.services.okf_engine import get_okf_store
        from app.services.llm_client import get_llm_client

        store = get_okf_store()
        clean_subj = re.sub(r"^(?:re|fwd|fw):\s*", "", message.subject or "", flags=re.IGNORECASE).strip()
        search_query = f"{clean_subj} {message.body_text}".strip()

        # Query native OKF concepts directly
        matching_concepts = store.search_concepts(search_query, k=3)

        if matching_concepts:
            # Clean titles for source chips (unique)
            seen_src = set()
            sources: List[str] = []
            for c in matching_concepts:
                ct = _clean_notion_title(c.title)
                if ct not in seen_src:
                    seen_src.add(ct)
                    sources.append(ct)

            blocks = []
            for c in matching_concepts:
                raw_c = c.description + "\n" + c.content[:1200]
                blocks.append(f"[{_clean_notion_title(c.title)}]\n{_clean_notion_content(raw_c)}")
            context_block = "\n\n".join(blocks)

            llm_client = get_llm_client()
            system_prompt = (
                "You are the official Legal & Policy AI Assistant for GOBITSNBYTES FOUNDATION (bits&bytes™).\n"
                "Answer the user's question clearly, concisely, and professionally using ONLY the provided approved Foundation policy context.\n"
                "Formatting guidelines:\n"
                "- Directly address the question with actionable, clear advice.\n"
                "- Structure your answer with clear paragraphs or bullet points where explaining rules.\n"
                "- Mention policy names cleanly (e.g., 'Under the Foundation Operating Manual...').\n"
                "- Do NOT output raw hex hashes (like Notion UUIDs), internal file paths, or document boilerplate.\n"
                "- Maintain a helpful, professional tone suited for internal leadership and team members."
            )
            user_prompt = f"Question: {message.body_text or search_query}\n\nApproved Foundation Policy Context:\n{context_block}"

            answer: Optional[str] = None
            try:
                raw_llm = llm_client._chat_completion([
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ])
                if raw_llm and raw_llm.strip():
                    answer = raw_llm.strip()
            except Exception as llm_err:
                logger.warning("[LegalAgent] LLM policy synthesis failed (%s), using fallback.", llm_err)

            if not answer:
                bullets = "\n".join(
                    f"- **{_clean_notion_title(c.title)}**: {_truncate(_clean_notion_content(c.description or c.content), 240)}"
                    for c in matching_concepts
                )
                answer = (
                    "Based on approved Foundation policy guidelines:\n\n"
                    f"{bullets}"
                )
        else:
            sources = []
            answer = (
                "I could not find an approved Foundation policy source matching that question. "
                "Please name the relevant policy topic (such as sponsorships, safeguarding, "
                "financial rules, or fork agreement) or attach an agreement for automated legal review."
            )

        await _send_policy_reply(settings, message, answer, sources=sources)
        return True

    shared_meta = {
        "message_id": message.message_id,
        "from": message.from_addr,
        "subject": message.subject,
        "received_at": message.received_at.isoformat(),
    }

    for filename, content_type, content in message.attachments:
        contract = await analyze_contract_bytes(
            db,
            filename,
            content,
            source="inbound_email",
            source_meta=dict(shared_meta),
        )

        db.add(
            ContractAssistantEvent(
                contract_id=contract.id,
                type=INBOUND_EVENT_TYPE,
                payload={
                    **shared_meta,
                    "attachment_filename": filename,
                    "attachment_content_type": content_type,
                    "contract_title": contract.title,
                },
            )
        )

        await _send_ingestion_reply(settings, message, contract)

    await db.commit()
    return True


def _clean_notion_title(title: str) -> str:
    """Remove 32-character hex UUID hashes appended by Notion page exports."""
    cleaned = re.sub(r"\b[0-9a-fA-F]{32}\b", "", title or "").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or (title or "").strip()


def _clean_notion_content(content: str) -> str:
    """Strip Notion hex hashes, duplicate header lines, and metadata banners."""
    if not content:
        return ""
    cleaned = re.sub(r"\b[0-9a-fA-F]{32}\b", "", content)
    lines: List[str] = []
    for line in cleaned.splitlines():
        line_str = line.strip()
        lower_line = line_str.lower()
        if lower_line.startswith("owner:"):
            continue
        if "official bits&bytes legal document from notion-wiki" in lower_line:
            continue
        if "official bits&bytes legal document" in lower_line:
            continue
        lines.append(line)
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _clean_bullet_text(line: str) -> str:
    return re.sub(r"^[-*•]\s*", "", line.strip())


def _clean_numbered_text(line: str) -> str:
    return re.sub(r"^\d+\.\s*", "", line.strip())


def _render_inline_markdown(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"__(.+?)__", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<em>\1</em>", escaped)
    escaped = re.sub(r"(?<!_)_([^_]+?)_(?!_)", r"<em>\1</em>", escaped)
    escaped = re.sub(
        r"`([^`]+?)`",
        r'<code style="background-color:#F5F3EF;padding:2px 5px;border-radius:3px;font-family:monospace;font-size:12px;color:#97192C;border:1px solid #E5E4E2;">\1</code>',
        escaped,
    )
    return escaped


def _render_markdown_paragraphs(text: str) -> str:
    """Convert markdown (headings, bold, lists, quotes, paragraphs) into responsive, polished email HTML."""
    cleaned = text.strip()
    if not cleaned:
        return ""

    raw_blocks = [b.strip() for b in re.split(r"\n\s*\n", cleaned) if b.strip()]
    rendered_parts: List[str] = []

    for block in raw_blocks:
        lines = block.splitlines()
        first_line = lines[0].strip()

        # Headings
        if first_line.startswith("# ") and len(lines) == 1:
            title = _render_inline_markdown(first_line[2:].strip())
            rendered_parts.append(
                f'<h2 style="margin:20px 0 10px 0;font-size:18px;font-weight:800;color:#97192C;letter-spacing:-0.01em;border-bottom:2px solid #FC920D;padding-bottom:6px;">{title}</h2>'
            )
            continue
        elif first_line.startswith("## ") and len(lines) == 1:
            title = _render_inline_markdown(first_line[3:].strip())
            rendered_parts.append(
                f'<h3 style="margin:18px 0 8px 0;font-size:15px;font-weight:700;color:#3C0A12;letter-spacing:-0.01em;">{title}</h3>'
            )
            continue
        elif first_line.startswith("### ") and len(lines) == 1:
            title = _render_inline_markdown(first_line[4:].strip())
            rendered_parts.append(
                f'<h4 style="margin:14px 0 6px 0;font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:0.04em;color:#716F6C;">{title}</h4>'
            )
            continue

        # Blockquotes
        if all(line.strip().startswith(">") for line in lines):
            quote_text = "<br/>".join(
                _render_inline_markdown(re.sub(r"^>\s*", "", line.strip()))
                for line in lines
            )
            rendered_parts.append(
                f'<blockquote style="margin:14px 0;padding:10px 16px;border-left:4px solid #FC920D;background-color:#FAF8F5;color:#413F3B;font-size:13px;line-height:1.6;font-style:italic;">{quote_text}</blockquote>'
            )
            continue

        # Bullet lists
        if any(re.match(r"^[-*•]\s+", line.strip()) for line in lines):
            items: List[str] = []
            curr_item: List[str] = []
            for line in lines:
                stripped = line.strip()
                if re.match(r"^[-*•]\s+", stripped):
                    if curr_item:
                        items.append(" ".join(curr_item))
                    curr_item = [re.sub(r"^[-*•]\s*", "", stripped)]
                else:
                    curr_item.append(stripped)
            if curr_item:
                items.append(" ".join(curr_item))

            rendered_items = "".join(
                f'<li style="margin-bottom:8px;line-height:1.6;">{_render_inline_markdown(item)}</li>'
                for item in items
            )
            rendered_parts.append(
                f'<ul style="margin:12px 0 16px 20px;padding:0;font-size:14px;color:#120F0A;">{rendered_items}</ul>'
            )
            continue

        # Numbered lists
        if any(re.match(r"^\d+\.\s+", line.strip()) for line in lines):
            num_items: List[str] = []
            num_curr: List[str] = []
            for line in lines:
                stripped = line.strip()
                if re.match(r"^\d+\.\s+", stripped):
                    if num_curr:
                        num_items.append(" ".join(num_curr))
                    num_curr = [re.sub(r"^\d+\.\s*", "", stripped)]
                else:
                    num_curr.append(stripped)
            if num_curr:
                num_items.append(" ".join(num_curr))

            rendered_num = "".join(
                f'<li style="margin-bottom:8px;line-height:1.6;">{_render_inline_markdown(item)}</li>'
                for item in num_items
            )
            rendered_parts.append(
                f'<ol style="margin:12px 0 16px 20px;padding:0;font-size:14px;color:#120F0A;">{rendered_num}</ol>'
            )
            continue

        # Regular paragraphs
        p_html = "<br/>".join(_render_inline_markdown(line.strip()) for line in lines if line.strip())
        rendered_parts.append(
            f'<p style="margin:12px 0;font-size:14px;line-height:1.65;color:#120F0A;">{p_html}</p>'
        )

    return "\n".join(rendered_parts)


def build_policy_email_bodies(
    answer: str,
    sources: Optional[List[str]] = None,
) -> Tuple[str, str]:
    """Generate both plain-text and responsive branded HTML email bodies for policy responses."""
    text_lines = [
        "bits&bytes™ Legal Agent — GOBITSNBYTES FOUNDATION",
        "==================================================",
        "",
        answer.strip(),
    ]
    if sources:
        text_lines.append("")
        text_lines.append("Approved Policy References:")
        for s in sources:
            text_lines.append(f"• {s}")
    text_lines.extend([
        "",
        "--------------------------------------------------",
        "Notice: This is an internal policy summary, not final legal advice.",
        "Reply with a PDF or DOCX agreement for automated contract analysis.",
    ])
    text_body = "\n".join(text_lines)

    content_html = _render_markdown_paragraphs(answer)
    chips_html = ""
    if sources:
        chips = "".join(
            f'<span style="display:inline-block;background-color:#FEE9CF;color:#791423;border:1px solid #FC920D;border-radius:4px;padding:3px 8px;font-size:11px;font-weight:600;margin-right:6px;margin-bottom:6px;">{html.escape(s)}</span>'
            for s in sources
        )
        chips_html = f"""
        <div style="margin-top:20px;padding-top:16px;border-top:1px solid #E5E4E2;">
            <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:#716F6C;margin-bottom:8px;">Referenced Foundation Policies:</div>
            <div>{chips}</div>
        </div>
        """

    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1.0"/></head>
<body style="margin:0;padding:24px 12px;background-color:#FAF8F5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#120F0A;">
  <div style="max-width:600px;margin:0 auto;background-color:#ffffff;border:2px solid #120F0A;border-radius:10px;box-shadow:4px 4px 0px 0px #120F0A;overflow:hidden;">
    <div style="background-color:#97192C;padding:18px 24px;border-bottom:2px solid #120F0A;">
      <h2 style="margin:0;font-size:18px;font-weight:800;color:#ffffff;letter-spacing:-0.02em;">bits&amp;bytes™ Legal Agent</h2>
      <p style="margin:4px 0 0 0;font-size:12px;color:#FED39E;font-weight:500;">GOBITSNBYTES FOUNDATION · Internal Policy Advisory</p>
    </div>
    <div style="padding:24px;">
      {content_html}
      {chips_html}
    </div>
    <div style="background-color:#F5F3EF;border-top:1px solid #E5E4E2;padding:16px 24px;font-size:11px;line-height:1.5;color:#716F6C;">
      <p style="margin:0 0 4px 0;"><strong>Notice:</strong> This is an internal policy reference summary generated for verified team members, not final legal advice. Reply with a PDF or DOCX agreement for automated contract analysis.</p>
      <div style="margin-top:6px;color:#A09F9D;font-size:10px;">GOBITSNBYTES FOUNDATION · Registered Section 8 Non-Profit</div>
    </div>
  </div>
</body>
</html>"""
    return text_body, html_body


def _truncate(text: str, limit: int) -> str:
    cleaned = (text or "").strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def build_ingestion_summary(
    contract: ContractAssistantContract,
) -> Tuple[str, str]:
    """Plain-language HTML + text summary of a freshly analysed contract."""
    clauses = list(contract.clauses or [])
    findings = list(contract.findings or [])

    counts = {"high": 0, "medium": 0, "low": 0}
    for f in findings:
        if f.severity in counts:
            counts[f.severity] += 1

    top = sorted(findings, key=lambda f: _SEVERITY_RANK.get(f.severity, 99))[:3]

    lines = [
        f"I reviewed the attached contract and filed it in your pipeline as “{contract.title}”.",
        "",
        f"- Clauses detected: {len(clauses)}",
        f"- Risk tiers: {counts['high']} high, {counts['medium']} medium, {counts['low']} low",
    ]

    if top:
        lines.append("")
        lines.append("Top findings:")
        for idx, f in enumerate(top, 1):
            lines.append(
                f"{idx}. [{f.severity.upper()}] {_truncate(f.heading, 120)} — "
                f"{_truncate(f.plain_english, 300)}"
            )
    else:
        lines.append("")
        lines.append("No policy violations surfaced on the first pass.")

    lines.append("")
    lines.append("Reply ATTACH corrected version or APPROVE to dispatch for signature.")
    lines.append("")
    lines.append("— GOBITSNBYTES FOUNDATION Legal Agent")

    text_body = "\n".join(lines)

    finding_rows = "".join(
        f"<li style=\"margin-bottom:8px;\"><strong>[{(f.severity or 'low').upper()}]</strong> "
        f"{_truncate(f.heading, 120)}<br/><span style='color:#555;'>{_truncate(f.plain_english, 300)}</span></li>"
        for f in top
    )
    html_body = f"""<html><body style="font-family:Arial,sans-serif;color:#111;">
<p>{lines[0]}</p>
<ul>
<li><strong>Clauses detected:</strong> {len(clauses)}</li>
<li><strong>Risk tiers:</strong> {counts['high']} high, {counts['medium']} medium, {counts['low']} low</li>
</ul>
{'<p><strong>Top findings:</strong></p><ol>' + finding_rows + '</ol>' if finding_rows else '<p>No policy violations surfaced on the first pass.</p>'}
<p>{lines[-3]}</p>
<p style="color:#666;font-size:12px;">GOBITSNBYTES FOUNDATION · bits&amp;bytes™ Legal Agent</p>
</body></html>"""
    return text_body, html_body


def _send_mime_sync(
    smtp_host: str,
    smtp_port: int,
    username: Optional[str],
    password: Optional[str],
    envelope_from: str,
    mime_msg: MIMEMultipart,
    recipients: List[str],
    use_starttls: bool,
) -> None:
    with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
        if use_starttls:
            server.ehlo()
            server.starttls()
            server.ehlo()
        if username and password:
            server.login(username, password)
        server.sendmail(envelope_from, recipients, mime_msg.as_string())


def send_reply(
    settings: Settings,
    to_addr: str,
    subject: str,
    text_body: str,
    html_body: str,
    in_reply_to: Optional[str] = None,
    references: Optional[str] = None,
) -> bool:
    """Send a threaded reply from the org legal mailbox via SMTP.

    Kept local to this module (instead of extending ``meetings.send_smtp_email``)
    because reply semantics need In-Reply-To/References headers, must NOT force
    the audit CC, and meetings.py is owned by another workstream. Mirrors the
    primary-SMTP-then-Brevo-relay fallback chain. Logs delivery outcome only.
    """
    org = settings.legal_org_mailbox
    domain = org.split("@")[-1] if "@" in org else "gobitsnbytes.org"

    to_clean = (to_addr or "").strip().lower()
    if (
        not to_clean
        or to_clean == org.lower()
        or to_clean == "legal@gobitsnbytes.org"
        or any(to_clean.startswith(p) for p in ("mailer-daemon@", "postmaster@", "noreply@", "no-reply@", "bounces-", "bounce@"))
        or any(d in to_clean for d in ("sender-sib.com", "sendinblue.com"))
    ):
        logger.warning("[LegalAgent] Refusing to send reply to loop or daemon recipient: %s", to_addr)
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    msg["From"] = email.utils.formataddr(("GOBITSNBYTES FOUNDATION Legal", org))
    msg["To"] = to_addr
    msg["Message-ID"] = email.utils.make_msgid(domain=domain)
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg["Reply-To"] = org
    msg["Auto-Submitted"] = "auto-replied"
    msg["X-Auto-Response-Suppress"] = "All"
    msg["Precedence"] = "bulk"
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        combined_refs = f"{references or ''} {in_reply_to}".strip()
        if combined_refs:
            msg["References"] = combined_refs

    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    if not settings.smtp_host or not settings.smtp_user or not settings.smtp_pass:
        logger.warning("[LegalAgent] SMTP mailer not configured; reply not delivered.")
        return False

    try:
        _send_mime_sync(
            settings.smtp_host,
            settings.smtp_port,
            settings.smtp_user,
            settings.smtp_pass,
            org,
            msg,
            [to_addr],
            use_starttls=True,
        )
        logger.info("[LegalAgent] Reply delivered to %s", to_addr)
        return True
    except Exception as primary_err:
        logger.warning(
            "[LegalAgent] Primary SMTP dispatch failed (%s); trying Brevo relay fallback.",
            primary_err,
        )

    brevo_host = os.getenv("BREVO_SMTP_HOST", "smtp-relay.brevo.com")
    brevo_port = int(os.getenv("BREVO_SMTP_PORT", "587"))
    brevo_user = os.getenv("BREVO_SMTP_USER", settings.smtp_user)
    brevo_pass = os.getenv("BREVO_SMTP_PASS", settings.smtp_pass)
    if not brevo_user or not brevo_pass:
        logger.error("[LegalAgent] Brevo fallback credentials not configured; reply dropped.")
        return False
    try:
        _send_mime_sync(
            brevo_host,
            brevo_port,
            brevo_user,
            brevo_pass,
            org,
            msg,
            [to_addr],
            use_starttls=True,
        )
        logger.info("[LegalAgent] Reply delivered via Brevo relay fallback to %s", to_addr)
        return True
    except Exception as fallback_err:
        logger.error("[LegalAgent] All reply transports failed for %s: %s", to_addr, fallback_err)
        return False


async def _send_ingestion_reply(
    settings: Settings,
    message: LegalInboxMessage,
    contract: ContractAssistantContract,
) -> None:
    text_body, html_body = build_ingestion_summary(contract)
    try:
        await asyncio.to_thread(
            send_reply,
            settings,
            message.from_addr,
            message.subject or contract.title,
            text_body,
            html_body,
            message.in_reply_to,
            message.references,
        )
    except Exception:
        logger.exception("[LegalAgent] Unexpected failure while sending ingestion reply.")


async def _send_policy_reply(
    settings: Settings,
    message: LegalInboxMessage,
    body: str,
    sources: Optional[List[str]] = None,
) -> None:
    text_body, html_body = build_policy_email_bodies(body, sources)
    delivered = await asyncio.to_thread(
        send_reply,
        settings,
        message.from_addr,
        message.subject or "Policy Advisory",
        text_body,
        html_body,
        message.in_reply_to,
        message.references,
    )
    if not delivered:
        logger.warning("[LegalAgent] Policy reply could not be delivered for message %s", message.message_id)


# ---------------------------------------------------------------------------
# IMAP poller
# ---------------------------------------------------------------------------

class LegalInboxPoller:
    """Polls the configured legal mailbox for unseen contract emails."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()

    def _configured(self) -> bool:
        s = self.settings
        return bool(s.legal_inbox_imap_host and s.legal_inbox_imap_user and s.legal_inbox_imap_password)

    def _connect(self) -> imaplib.IMAP4_SSL:
        s = self.settings
        client = imaplib.IMAP4_SSL(s.legal_inbox_imap_host, s.legal_inbox_imap_port)
        client.login(s.legal_inbox_imap_user, s.legal_inbox_imap_password)
        return client

    def _fetch_unseen(self) -> List[Tuple[bytes, bytes]]:
        client = self._connect()
        batch: List[Tuple[bytes, bytes]] = []
        try:
            client.select(self.settings.legal_inbox_mailbox)
            typ, data = client.search(None, "UNSEEN")
            if typ != "OK":
                logger.error("[LegalAgent] IMAP SEARCH failed: %s", typ)
                return batch
            message_nums: List[bytes] = []
            for entry in data or []:
                if not entry:
                    continue
                if isinstance(entry, bytes):
                    message_nums.extend([n for n in entry.split() if n])
                elif isinstance(entry, str):
                    message_nums.extend([n.encode("utf-8") for n in entry.split() if n])

            for num in message_nums[-_MAX_MESSAGES_PER_POLL:]:
                typ_msg, fetched = client.fetch(num, "(RFC822)")
                if typ_msg != "OK" or not fetched:
                    continue
                for item in fetched:
                    if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], bytes):
                        batch.append((num, item[1]))
                        break
        finally:
            try:
                client.logout()
            except Exception:
                pass
        return batch

    def _mark_seen(self, num: bytes) -> None:
        client = self._connect()
        try:
            client.select(self.settings.legal_inbox_mailbox)
            client.store(num, "+FLAGS", "\\Seen")
        finally:
            try:
                client.logout()
            except Exception:
                pass

    async def poll_once(self, db: AsyncSession) -> int:
        """One poll cycle. Returns number of messages processed."""
        global _last_poll_at
        if not self._configured():
            logger.info("[LegalAgent] Legal inbox not fully configured; poll skipped.")
            return 0

        batch = await asyncio.to_thread(self._fetch_unseen)
        processed = 0

        for num, raw_bytes in batch:
            try:
                message = parse_message(raw_bytes)
                handled = await handle_inbox_message(db, self.settings, message)
                if handled:
                    await asyncio.to_thread(self._mark_seen, num)
                    processed += 1
            except Exception:
                logger.exception(
                    "[LegalAgent] Failed handling inbound message; leaving unread for retry."
                )
                try:
                    await db.rollback()
                except Exception:
                    pass

        _last_poll_at = datetime.now(timezone.utc)
        return processed

    async def run_forever(self) -> None:
        """Long-running loop with jittered sleeps; never raises."""
        from app.database import get_sessionmaker

        while True:
            delay = max(int(self.settings.legal_inbox_poll_seconds), 0)
            if delay == 0:
                logger.info("[LegalAgent] Polling disabled (poll_seconds=0); loop exiting.")
                return
            session_factory = get_sessionmaker()
            async with session_factory() as db:
                try:
                    await self.poll_once(db)
                except Exception:
                    logger.exception("[LegalAgent] Inbox poll cycle failed; continuing.")
            jitter = random.uniform(0, min(delay * 0.25, 15))
            await asyncio.sleep(delay + jitter)


# ---------------------------------------------------------------------------
# Signature nudge sequencer (3d / 7d / 14d)
# ---------------------------------------------------------------------------

@dataclass
class NudgeTarget:
    request_id: uuid.UUID
    recipient_id: uuid.UUID
    contract_id: Optional[uuid.UUID]
    title: str
    name: str
    email: str
    access_token: str
    cadence_day: int
    staleness_days: int


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _naive_utc(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


async def collect_nudge_targets(
    db: AsyncSession,
    now: Optional[datetime] = None,
) -> List[NudgeTarget]:
    """Compute signatories due for a reminder right now (no side effects)."""
    now = _as_utc(now) or datetime.now(timezone.utc)

    req_stmt = (
        select(SignatureRequest)
        .options(selectinload(SignatureRequest.recipients))
        .where(SignatureRequest.status == "pending")
    )
    requests = (await db.execute(req_stmt)).scalars().all()
    if not requests:
        return []

    request_ids = [r.id for r in requests]

    env_stmt = select(ContractAssistantEnvelope).where(
        ContractAssistantEnvelope.signature_request_id.in_(request_ids)
    )
    envelopes = {e.signature_request_id: e for e in (await db.execute(env_stmt)).scalars().all()}

    audit_stmt = select(SignatureAuditLog).where(SignatureAuditLog.request_id.in_(request_ids))
    last_activity: Dict[uuid.UUID, datetime] = {}
    for audit in (await db.execute(audit_stmt)).scalars():
        if audit.recipient_id is None or audit.action not in ("otp_requested", "viewed", "created"):
            continue
        stamp = _as_utc(audit.created_at)
        if stamp and (audit.recipient_id not in last_activity or stamp > last_activity[audit.recipient_id]):
            last_activity[audit.recipient_id] = stamp

    contract_ids = [e.contract_id for e in envelopes.values()]
    nudge_history: Dict[Tuple[str, str], Dict[str, Any]] = {}
    if contract_ids:
        hist_stmt = select(ContractAssistantEvent).where(
            ContractAssistantEvent.type == REMINDER_EVENT_TYPE,
            ContractAssistantEvent.contract_id.in_(contract_ids),
        )
        for evt in (await db.execute(hist_stmt)).scalars():
            payload = evt.payload if isinstance(evt.payload, dict) else {}
            key = (str(evt.contract_id), str(payload.get("recipient_id", "")))
            entry = nudge_history.setdefault(key, {"count": 0, "days": []})
            entry["count"] += 1
            day = payload.get("cadence_day")
            if isinstance(day, int):
                entry["days"].append(day)

    targets: List[NudgeTarget] = []
    for request in requests:
        envelope = envelopes.get(request.id)
        if envelope is None:
            continue  # unlinked request — skip gracefully

        for recipient in request.recipients:
            if recipient.status not in ("pending", "viewed"):
                continue  # signed / declined / revoked — stop condition

            base = last_activity.get(recipient.id) or _as_utc(request.created_at) or now
            staleness_days = (now - base).days

            history = nudge_history.get(
                (str(envelope.contract_id), str(recipient.id)), {"count": 0, "days": []}
            )
            if history["count"] >= MAX_NUDGES_PER_RECIPIENT:
                continue

            due_days = [
                d for d in NUDGE_CADENCE_DAYS if d <= staleness_days and d not in history["days"]
            ]
            if not due_days:
                continue

            targets.append(
                NudgeTarget(
                    request_id=request.id,
                    recipient_id=recipient.id,
                    contract_id=envelope.contract_id,
                    title=request.title,
                    name=recipient.name,
                    email=recipient.email,
                    access_token=recipient.access_token,
                    cadence_day=max(due_days),
                    staleness_days=max(staleness_days, 0),
                )
            )

    return targets


def build_nudge_email(target: NudgeTarget, base_url: str) -> Tuple[str, str, str]:
    """Branded minimal reminder: returns (subject, text, html)."""
    sign_url = f"{base_url}/sign/{target.access_token}"
    waiting = target.staleness_days
    subject = f"Gentle reminder: “{target.title}” is awaiting your signature"
    text = (
        f"Hello {target.name},\n\n"
        f"Our records show “{target.title}” has been waiting for your signature "
        f"for about {waiting} day(s).\n\nSign here: {sign_url}\n\n"
        "— GOBITSNBYTES FOUNDATION legal portal"
    )
    html = f"""<html><body style="font-family:Arial,sans-serif;background:#FAF8F5;padding:20px;">
<div style="max-width:520px;margin:0 auto;background:#ffffff;border:2px solid #120F0A;border-radius:10px;padding:22px;">
<h2 style="color:#97192C;margin-top:0;">Signature reminder</h2>
<p>Hello <strong>{target.name}</strong>,</p>
<p>“{target.title}” has been awaiting your signature for about <strong>{waiting} day(s)</strong>.</p>
<div style="text-align:center;margin:24px 0;">
<a href="{sign_url}" style="background:#97192C;color:#fff;padding:12px 26px;text-decoration:none;border-radius:6px;font-weight:bold;border:2px solid #120F0A;">Review &amp; Sign</a>
</div>
<p style="font-size:11px;color:#716F6C;">Direct link: <a href="{sign_url}" style="color:#97192C;">{sign_url}</a></p>
<hr style="border:none;border-top:1px solid #ddd;margin:18px 0;"/>
<p style="font-size:11px;color:#716F6C;margin-bottom:0;">GOBITSNBYTES FOUNDATION legal portal · legal@gobitsnbytes.org</p>
</div></body></html>"""
    return subject, text, html


async def send_signature_nudge(db: AsyncSession, target: NudgeTarget) -> bool:
    """Deliver one reminder and persist its state (events + IAM audit)."""
    from app.routers.meetings import send_smtp_email

    settings = get_settings()
    subject, text_body, html_body = build_nudge_email(target, settings.nextauth_url)

    delivered = False
    try:
        await asyncio.to_thread(
            send_smtp_email,
            settings,
            [target.email],
            subject,
            html_body,
        )
        delivered = True
    except Exception:
        logger.exception("[LegalAgent] Reminder transport failed for recipient %s", target.recipient_id)
        return False

    if target.contract_id is not None:
        db.add(
            ContractAssistantEvent(
                contract_id=target.contract_id,
                type=REMINDER_EVENT_TYPE,
                payload={
                    "recipient_id": str(target.recipient_id),
                    "request_id": str(target.request_id),
                    "cadence_day": target.cadence_day,
                    "sent_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        )

    from app.iam.audit import write_audit_entry

    await write_audit_entry(
        db,
        actor_id=None,
        action="signature.reminder_sent",
        target_type="signature_request",
        target_id=str(target.request_id),
        metadata={"recipient_id": str(target.recipient_id), "cadence_day": target.cadence_day},
    )

    await db.commit()
    logger.info(
        "[LegalAgent] Reminder sent (%dd cadence) for request %s recipient %s",
        target.cadence_day,
        target.request_id,
        target.recipient_id,
    )
    return delivered


async def run_nudge_cycle(db: AsyncSession, now: Optional[datetime] = None) -> List[NudgeTarget]:
    """Full nudge pass; returns the targets that were actually reminded."""
    if not get_settings().legal_nudge_enabled:
        return []

    targets = await collect_nudge_targets(db, now=now)
    sent: List[NudgeTarget] = []
    for target in targets:
        try:
            if await send_signature_nudge(db, target):
                sent.append(target)
        except Exception:
            logger.exception("[LegalAgent] Nudge cycle error for recipient %s", target.recipient_id)
            try:
                await db.rollback()
            except Exception:
                pass
    return sent


# ---------------------------------------------------------------------------
# Scheduled job wrappers + scheduler lifecycle (mirrors provisioning.scheduler)
# ---------------------------------------------------------------------------

async def legal_inbox_poll_job() -> None:
    from app.database import get_sessionmaker

    session_factory = get_sessionmaker()
    async with session_factory() as session:
        try:
            await LegalInboxPoller().poll_once(session)
        except Exception as err:
            logger.error("Scheduled legal inbox poll failed: %s", err)


async def signature_nudge_job() -> None:
    from app.database import get_sessionmaker

    session_factory = get_sessionmaker()
    async with session_factory() as session:
        try:
            await run_nudge_cycle(session)
        except Exception as err:
            logger.error("Scheduled signature nudge job failed: %s", err)


_scheduler: Any = None


async def start_legal_agent_jobs() -> None:
    """Register inbox-poller + nudge jobs on an APScheduler instance."""
    global _scheduler
    if _scheduler is not None:
        logger.warning("Legal Agent scheduler is already running.")
        return

    settings = get_settings()

    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    _scheduler = AsyncIOScheduler()

    poll_seconds = int(settings.legal_inbox_poll_seconds)
    imap_ready = bool(
        settings.legal_inbox_imap_host
        and settings.legal_inbox_imap_user
        and settings.legal_inbox_imap_password
    )
    if poll_seconds > 0 and imap_ready:
        _scheduler.add_job(
            legal_inbox_poll_job,
            "interval",
            seconds=poll_seconds,
            id="legal_inbox_poll_job",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        logger.info("Legal inbox poller scheduled every %ds.", poll_seconds)
    else:
        logger.info("Legal inbox poller not scheduled (configured=%s, poll_seconds=%d).", imap_ready, poll_seconds)

    if settings.legal_nudge_enabled:
        _scheduler.add_job(
            signature_nudge_job,
            "interval",
            hours=1,
            id="legal_signature_nudge_job",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        logger.info("Signature nudge job scheduled hourly.")

    _scheduler.start()


async def stop_legal_agent_jobs() -> None:
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.shutdown()
    _scheduler = None
    logger.info("Legal Agent scheduler stopped.")
