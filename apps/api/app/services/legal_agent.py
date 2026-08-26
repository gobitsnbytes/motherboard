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
import imaplib
import logging
import os
import random
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

    Walks multipart trees, decodes the first text/plain body, and extracts
    contract-document attachments (pdf/docx/doc, including octet-stream parts
    that carry a document filename).
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

    body_text = ""
    attachments: List[Tuple[str, str, bytes]] = []

    for part in msg.walk():
        if part.is_multipart():
            continue
        content_type = part.get_content_type()
        filename = _decode_mime_header(part.get_filename())
        disposition = (part.get("Content-Disposition") or "").lower()

        if content_type == "text/plain" and not filename and "attachment" not in disposition:
            payload = part.get_payload(decode=True)
            if payload:
                charset = part.get_content_charset() or "utf-8"
                body_text += payload.decode(charset, errors="replace")
            continue

        if filename or "attachment" in disposition:
            payload = part.get_payload(decode=True) or b""
            if _is_contract_attachment(filename, content_type):
                attachments.append((filename or "attachment.pdf", content_type, payload))

    return LegalInboxMessage(
        message_id=msg.get("Message-ID"),
        in_reply_to=msg.get("In-Reply-To"),
        references=msg.get("References"),
        from_addr=from_addr,
        subject=subject,
        body_text=body_text.strip(),
        attachments=attachments[:_MAX_ATTACHMENTS_PER_MESSAGE],
        received_at=received_at,
    )


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

    if await is_duplicate_inbound(db, message.message_id):
        logger.info("[LegalAgent] Skipping duplicate Message-ID %s", message.message_id)
        return True

    if not message.attachments:
        logger.info(
            "[LegalAgent] No contract attachments in message %s; marking seen.",
            message.message_id,
        )
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

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    msg["From"] = email.utils.formataddr(("GOBITSNBYTES FOUNDATION Legal", org))
    msg["To"] = to_addr
    msg["Message-ID"] = email.utils.make_msgid(domain=domain)
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
            for num in (data or [])[-_MAX_MESSAGES_PER_POLL:]:
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
