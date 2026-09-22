"""Mailroom: lightweight live webmail over the existing Dovecot server.

Four units live in this file because the plugin loader ``exec``s ``main.py``
with no package context, so sibling imports are not available:

* ``auth``      -- credential checks, sign-in codes, mailbox selection
* ``mailbox``   -- IMAP reads and writes, MIME to API shape
* ``sender``    -- authenticated submission plus Sent/Drafts append
* ``assistant`` -- bounded message context to SparkCloud

Dovecot stays the source of truth. Nothing here writes mail content to
PostgreSQL; the only persisted secrets are the mailbox password (encrypted)
and a keyed digest of the current sign-in code.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import email
import hashlib
import hmac
import imaplib
import json
import quopri
import re
import secrets
import smtplib
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from email.header import decode_header
from email.message import EmailMessage, Message
from email.utils import formataddr, formatdate, getaddresses, make_msgid, parsedate_to_datetime
from typing import Any, Iterator
from urllib.parse import urlencode

import nh3
from fastapi import APIRouter, Header, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.db.models import Group, MailroomAccount, MailroomOtpChallenge
from app.dependencies import CurrentUserDep, DbSession
from app.plugin_sdk.types import PluginManifest, UiPanelDeclaration
from app.services.llm_client import get_llm_client


router = APIRouter()

# Folder names are passed straight into IMAP commands, so the character set is
# kept to what cannot terminate a quoted string.
SAFE_MAILBOX = re.compile(r"^[A-Za-z0-9 ._/-]{1,80}$")
SAFE_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")

# The web proxy gives up on the backend at 8s, so every mail round trip has to
# finish inside that.
IMAP_TIMEOUT_SECONDS = 6
SMTP_TIMEOUT_SECONDS = 6

OTP_LENGTH = 6
OTP_TTL = timedelta(minutes=10)
OTP_RESEND_INTERVAL = timedelta(seconds=60)
OTP_MAX_ATTEMPTS = 5

SNIPPET_BYTES = 500
ASSISTANT_THREAD_MESSAGES = 6
ASSISTANT_CHARS_PER_MESSAGE = 4000

IDEMPOTENCY_HEADER = "X-Mailroom-Idempotency"
DRAFT_HEADER = "X-Mailroom-Draft"

# Dovecot's namespace declares these; Archive is created on first use.
SENT_FOLDER = "Sent"
DRAFTS_FOLDER = "Drafts"
TRASH_FOLDER = "Trash"
ARCHIVE_FOLDER = "Archive"

# IMAP is blocking. A bounded pool keeps a slow mail host from consuming every
# thread FastAPI has.
_imap_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="mailroom")


async def _in_worker(fn, *args):
    """Run one blocking mail operation on the bounded pool."""
    return await asyncio.get_running_loop().run_in_executor(_imap_pool, fn, *args)


# ---------------------------------------------------------------------------
# API shapes
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=1, max_length=512)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class OtpRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class OtpVerifyRequest(OtpRequest):
    code: str = Field(pattern=rf"^\d{{{OTP_LENGTH}}}$")


class AiPreferences(BaseModel):
    tone: str = Field(default="neutral", max_length=40)
    signature: str = Field(default="", max_length=500)
    auto_triage: bool = False


class SessionResponse(BaseModel):
    authenticated: bool
    email: str | None = None
    accounts: list[str] = Field(default_factory=list)
    preferences: AiPreferences = Field(default_factory=AiPreferences)


class Folder(BaseModel):
    name: str
    display_name: str
    role: str | None = None
    total: int
    unread: int


class MessageSummary(BaseModel):
    uid: str
    folder: str
    sender: str
    to: str
    subject: str
    date: str | None
    unread: bool
    flagged: bool
    has_attachments: bool
    snippet: str


class MessageListResponse(BaseModel):
    folder: str
    total: int
    offset: int
    messages: list[MessageSummary]


class Attachment(BaseModel):
    index: int
    filename: str
    content_type: str
    size: int


class LinkTarget(BaseModel):
    href: str
    text: str


class ThreadNeighbour(BaseModel):
    uid: str
    subject: str
    sender: str
    date: str | None


class MessageResponse(BaseModel):
    uid: str
    folder: str
    message_id: str | None
    sender: str
    to: str
    cc: str
    subject: str
    date: str | None
    text: str
    html: str | None
    remote_images_blocked: int
    links: list[LinkTarget]
    attachments: list[Attachment]
    thread: list[ThreadNeighbour]


class FlagUpdate(BaseModel):
    seen: bool | None = None
    flagged: bool | None = None


class MoveRequest(BaseModel):
    folder: str = Field(min_length=1, max_length=80)


class Draft(BaseModel):
    to: str = Field(default="", max_length=2000)
    cc: str = Field(default="", max_length=2000)
    bcc: str = Field(default="", max_length=2000)
    subject: str = Field(default="", max_length=500)
    body: str = Field(default="", max_length=200_000)
    in_reply_to: str | None = Field(default=None, max_length=500)
    references: str | None = Field(default=None, max_length=4000)


class SaveDraftRequest(Draft):
    replaces_uid: str | None = Field(default=None, max_length=20)


class SaveDraftResponse(BaseModel):
    uid: str | None


class SendResponse(BaseModel):
    message_id: str
    duplicate: bool


class AssistantRequest(BaseModel):
    action: str = Field(pattern="^(summarize|reply|rewrite|triage)$")
    folder: str = Field(default="INBOX", max_length=80)
    uid: str | None = Field(default=None, max_length=20)
    instruction: str = Field(default="", max_length=2000)
    draft: str = Field(default="", max_length=50_000)


class AssistantResponse(BaseModel):
    action: str
    summary: str | None = None
    body: str | None = None
    suggestion: str | None = None
    reason: str | None = None


# ---------------------------------------------------------------------------
# Shared MIME helpers
# ---------------------------------------------------------------------------


def _decode(value: str | None) -> str:
    if not value:
        return ""
    chunks: list[str] = []
    for part, charset in decode_header(value):
        if isinstance(part, bytes):
            chunks.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            chunks.append(part)
    return "".join(chunks).strip()


def _body_part(message: Message, content_type: str) -> Message | None:
    """First non-attachment part of ``content_type``, or None."""
    if not message.is_multipart():
        return message if message.get_content_type() == content_type else None
    for part in message.walk():
        if part.get_content_type() != content_type:
            continue
        if "attachment" in (part.get("Content-Disposition") or "").lower():
            continue
        return part
    return None


def _part_text(part: Message | None) -> str:
    if part is None:
        return ""
    payload = part.get_payload(decode=True) or b""
    return payload.decode(part.get_content_charset() or "utf-8", errors="replace")


def _plain_text(message: Message) -> str:
    return _part_text(_body_part(message, "text/plain"))


def _date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.isoformat()
    except (TypeError, ValueError, OverflowError):
        return value


# ---------------------------------------------------------------------------
# Safe rendering
# ---------------------------------------------------------------------------

ALLOWED_TAGS = {
    "a", "abbr", "b", "blockquote", "br", "caption", "code", "col", "colgroup",
    "dd", "div", "dl", "dt", "em", "figcaption", "figure", "h1", "h2", "h3",
    "h4", "h5", "h6", "hr", "i", "img", "li", "ol", "p", "pre", "q", "s",
    "small", "span", "strong", "sub", "sup", "table", "tbody", "td", "tfoot",
    "th", "thead", "tr", "u", "ul",
}

# Both the tag and everything inside it go. Scripts, styles, and anything that
# can make the browser fetch or submit on its own.
DROPPED_WITH_CONTENT = {
    "base", "embed", "form", "head", "iframe", "link", "meta", "noscript",
    "object", "script", "style", "svg", "template", "title",
}

ALLOWED_ATTRIBUTES = {
    "a": {"href", "title"},
    "img": {"src", "alt", "width", "height"},
    "td": {"colspan", "rowspan", "align"},
    "th": {"colspan", "rowspan", "align"},
    "col": {"span"},
    "colgroup": {"span"},
}

# An allowlist, so position/fixed and anything that can paint outside the
# message surface is simply absent.
ALLOWED_STYLE_PROPERTIES = {
    "color", "background-color", "font-weight", "font-style", "font-size",
    "text-align", "text-decoration", "margin", "padding", "border",
    "border-collapse", "line-height", "width", "max-width",
}

SAFE_LINK_SCHEMES = {"http", "https", "mailto"}
# nh3 checks schemes before the attribute filter runs, so "cid" has to survive
# that pass for inline images to be rewritten. The filter below only ever maps
# it onto an img src; anywhere else it is dropped.
SANITIZER_URL_SCHEMES = SAFE_LINK_SCHEMES | {"cid"}


def _is_safe_link(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered.startswith(("/", "#")):
        return True
    scheme, separator, _ = lowered.partition(":")
    if not separator:
        return True
    return scheme in SAFE_LINK_SCHEMES


def _sanitize_html(
    raw: str, inline_images: dict[str, str], allow_remote: bool
) -> tuple[str, int, list[LinkTarget]]:
    """Return sanitized HTML, the count of blocked remote images, and links.

    ``inline_images`` maps a bare Content-ID to the authenticated attachment
    URL that serves it. Remote images start blocked; the caller opts in per
    message.
    """
    blocked = 0
    links: list[LinkTarget] = []

    def attribute_filter(tag: str, attribute: str, value: str) -> str | None:
        nonlocal blocked
        if attribute == "style":
            return value
        if value.lower().startswith("cid:") and not (tag == "img" and attribute == "src"):
            return None
        if tag == "img" and attribute == "src":
            if value.lower().startswith("cid:"):
                return inline_images.get(value[4:].strip().strip("<>"))
            if not _is_safe_link(value):
                return None
            if not allow_remote:
                blocked += 1
                return None
            return value
        if tag == "a" and attribute == "href":
            if not _is_safe_link(value):
                return None
            links.append(LinkTarget(href=value, text=value))
            return value
        return value

    cleaned = nh3.clean(
        raw,
        tags=ALLOWED_TAGS,
        clean_content_tags=DROPPED_WITH_CONTENT,
        attributes={**ALLOWED_ATTRIBUTES, "*": {"style"}},
        attribute_filter=attribute_filter,
        filter_style_properties=ALLOWED_STYLE_PROPERTIES,
        url_schemes=SANITIZER_URL_SCHEMES,
        link_rel="noopener noreferrer nofollow",
        set_tag_attribute_values={"a": {"target": "_blank"}},
        strip_comments=True,
    )
    return cleaned, blocked, links


_TAG = re.compile(r"<[^>]+>")


def _html_to_text(raw: str) -> str:
    stripped = _TAG.sub(" ", raw.replace("<br>", "\n").replace("</p>", "\n"))
    return re.sub(r"[ \t]+", " ", stripped).strip()


# ---------------------------------------------------------------------------
# Unit 1: auth
# ---------------------------------------------------------------------------


@contextmanager
def _imap(account: MailroomAccount) -> Iterator[imaplib.IMAP4_SSL]:
    settings = get_settings()
    client = imaplib.IMAP4_SSL(
        settings.mailroom_imap_host,
        settings.mailroom_imap_port,
        timeout=IMAP_TIMEOUT_SECONDS,
    )
    try:
        client.login(account.email, account.password)
        yield client
    finally:
        try:
            client.logout()
        except (imaplib.IMAP4.error, OSError):
            pass


def _verify_credentials(address: str, password: str) -> None:
    settings = get_settings()
    with imaplib.IMAP4_SSL(
        settings.mailroom_imap_host,
        settings.mailroom_imap_port,
        timeout=IMAP_TIMEOUT_SECONDS,
    ) as client:
        client.login(address, password)


def _hash_code(code: str) -> str:
    """Keyed digest, so a database copy alone cannot be brute-forced offline."""
    secret = get_settings().session_secret.encode()
    return hmac.new(secret, code.encode(), hashlib.sha256).hexdigest()


async def _available_accounts(
    db: DbSession, principal: CurrentUserDep, personal: MailroomAccount | None
) -> list[str]:
    accounts = [personal.email] if personal else []
    settings = get_settings()
    group_slugs = set(
        (await db.scalars(select(Group.slug).where(Group.id.in_(principal.group_ids)))).all()
    ) if principal.group_ids else set()
    may_use_shared = principal.is_super_admin or "sg_executive" in group_slugs
    hello_password = settings.mailroom_hello_password
    if not hello_password and settings.smtp_user == "hello@gobitsnbytes.org":
        hello_password = settings.smtp_pass
    if may_use_shared and hello_password:
        accounts.append("hello@gobitsnbytes.org")
    if may_use_shared and settings.mailroom_legal_password:
        accounts.append("legal@gobitsnbytes.org")
    return list(dict.fromkeys(accounts))


async def _selected_account(
    db: DbSession,
    principal: CurrentUserDep,
    requested: str | None,
) -> MailroomAccount:
    personal = await db.scalar(
        select(MailroomAccount).where(MailroomAccount.user_id == principal.user_id)
    )
    available = await _available_accounts(db, principal, personal)
    selected = (requested or (personal.email if personal else "")).lower()
    if selected not in available:
        if personal is None and not available:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in to Mailroom")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Mailbox access denied")
    if personal is not None and selected == personal.email:
        return personal
    settings = get_settings()
    password = (
        settings.mailroom_hello_password
        or (settings.smtp_pass if settings.smtp_user == "hello@gobitsnbytes.org" else None)
    ) if selected == "hello@gobitsnbytes.org" else settings.mailroom_legal_password
    if not password:
        raise HTTPException(status_code=404, detail="Shared mailbox is not configured")
    return MailroomAccount(user_id=principal.user_id, email=selected, password=password)


def _check_domain(address: str) -> None:
    suffix = f"@{get_settings().mailroom_domain.lower()}"
    if not address.endswith(suffix) or address.count("@") != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Use your {suffix} address"
        )


def _preferences(account: MailroomAccount | None) -> AiPreferences:
    if account is None:
        return AiPreferences()
    return AiPreferences.model_validate(account.ai_preferences or {})


# ---------------------------------------------------------------------------
# Unit 2: mailbox
# ---------------------------------------------------------------------------

_FOLDER_ROLES = {
    "\\sent": "sent",
    "\\drafts": "drafts",
    "\\trash": "trash",
    "\\junk": "junk",
    "\\archive": "archive",
}
_LIST_LINE = re.compile(rb'^\((?P<flags>[^)]*)\) "(?P<sep>[^"]*)" (?P<name>.+)$')


def _check_folder(name: str) -> str:
    if not SAFE_MAILBOX.fullmatch(name):
        raise HTTPException(status_code=400, detail="Invalid mailbox")
    return name


def _quote(name: str) -> str:
    """Folder names reach IMAP as quoted strings; SAFE_MAILBOX bars the escapes."""
    return f'"{name}"'


def _ok(result: str, message: str = "Mail server rejected that request") -> None:
    if result != "OK":
        raise HTTPException(status_code=502, detail=message)


def _select(client: imaplib.IMAP4_SSL, folder: str, readonly: bool = True) -> int:
    result, data = client.select(_quote(folder), readonly=readonly)
    if result != "OK":
        raise HTTPException(status_code=404, detail="Mailbox not found")
    return int(data[0]) if data and data[0] else 0


def _list_folders(account: MailroomAccount) -> list[Folder]:
    with _imap(account) as client:
        result, rows = client.list()
        _ok(result, "Could not list mail folders")
        folders: list[Folder] = []
        for row in rows or []:
            if not isinstance(row, bytes):
                continue
            match = _LIST_LINE.match(row.strip())
            if not match:
                continue
            flags = match.group("flags").decode("ascii", errors="ignore").lower().split()
            if "\\noselect" in flags:
                continue
            name = match.group("name").decode("utf-8", errors="replace").strip().strip('"')
            if not SAFE_MAILBOX.fullmatch(name):
                continue
            separator = match.group("sep").decode("ascii", errors="ignore") or "/"
            role = next((_FOLDER_ROLES[flag] for flag in flags if flag in _FOLDER_ROLES), None)
            if name.upper() == "INBOX":
                role = "inbox"
            status_result, status_rows = client.status(_quote(name), "(MESSAGES UNSEEN)")
            total = unread = 0
            if status_result == "OK" and status_rows:
                counts = dict(
                    re.findall(rb"(MESSAGES|UNSEEN) (\d+)", status_rows[0] or b"")
                )
                total = int(counts.get(b"MESSAGES", 0))
                unread = int(counts.get(b"UNSEEN", 0))
            folders.append(Folder(
                name=name,
                display_name="Inbox" if role == "inbox" else name.rsplit(separator, 1)[-1],
                role=role,
                total=total,
                unread=unread,
            ))
        folders.sort(key=lambda f: (f.role != "inbox", f.display_name.lower()))
        return folders


_UID_IN_RESPONSE = re.compile(rb"UID (\d+)")
_BASE64_ONLY = re.compile(rb"^[A-Za-z0-9+/=\s]+$")


def _decode_snippet(chunk: bytes) -> str:
    """Best-effort preview text from a partial body fetch.

    ponytail: the transfer encoding is not fetched, so this guesses from the
    bytes. Pull BODYSTRUCTURE into the summary fetch if previews come out wrong.
    """
    if not chunk:
        return ""
    if len(chunk) > 16 and _BASE64_ONLY.fullmatch(chunk):
        try:
            chunk = base64.b64decode(chunk + b"===", validate=False)
        except (binascii.Error, ValueError):
            pass
    elif b"=" in chunk:
        try:
            chunk = quopri.decodestring(chunk)
        except ValueError:
            pass
    text = chunk.decode("utf-8", errors="replace")
    if "<" in text and ">" in text:
        text = _html_to_text(text)
    return " ".join(text.split())[:180]


def _fetch_parts(
    client: imaplib.IMAP4_SSL, uid_set: bytes, spec: str
) -> dict[str, bytes]:
    """One FETCH over a UID set, keyed by UID.

    Each spec requests a single literal so imaplib's response stays a flat list
    of (preamble, literal) tuples, which is the only shape it parses reliably.
    """
    result, rows = client.uid("fetch", uid_set, spec)
    _ok(result, "Could not read that mailbox")
    parsed: dict[str, bytes] = {}
    for row in rows or []:
        if not isinstance(row, tuple):
            continue
        match = _UID_IN_RESPONSE.search(row[0] or b"")
        if match:
            parsed[match.group(1).decode("ascii")] = row[1] or b""
    return parsed


def _fetch_flags(client: imaplib.IMAP4_SSL, uid_set: bytes) -> dict[str, str]:
    result, rows = client.uid("fetch", uid_set, "(UID FLAGS)")
    _ok(result, "Could not read message flags")
    flags: dict[str, str] = {}
    for row in rows or []:
        line = row[0] if isinstance(row, tuple) else row
        if not isinstance(line, bytes):
            continue
        match = _UID_IN_RESPONSE.search(line)
        if match:
            flags[match.group(1).decode("ascii")] = line.decode("ascii", errors="ignore")
    return flags


SUMMARY_HEADERS = (
    "(UID BODY.PEEK[HEADER.FIELDS "
    "(FROM TO SUBJECT DATE MESSAGE-ID CONTENT-TYPE)])"
)


def _summaries(
    client: imaplib.IMAP4_SSL, folder: str, uids: list[bytes]
) -> list[MessageSummary]:
    if not uids:
        return []
    uid_set = b",".join(uids)
    headers = _fetch_parts(client, uid_set, SUMMARY_HEADERS)
    snippets = _fetch_parts(client, uid_set, f"(UID BODY.PEEK[1]<0.{SNIPPET_BYTES}>)")
    flags = _fetch_flags(client, uid_set)

    summaries: list[MessageSummary] = []
    for raw_uid in uids:
        uid = raw_uid.decode("ascii")
        parsed = email.message_from_bytes(headers.get(uid, b""))
        flag_line = flags.get(uid, "")
        content_type = (parsed.get("Content-Type") or "").lower()
        summaries.append(MessageSummary(
            uid=uid,
            folder=folder,
            sender=_decode(parsed.get("From")),
            to=_decode(parsed.get("To")),
            subject=_decode(parsed.get("Subject")) or "(no subject)",
            date=_date(parsed.get("Date")),
            unread="\\Seen" not in flag_line,
            flagged="\\Flagged" in flag_line,
            has_attachments="multipart/mixed" in content_type,
            snippet=_decode_snippet(snippets.get(uid, b"")),
        ))
    return summaries


def _search_uids(client: imaplib.IMAP4_SSL, *criteria) -> list[bytes]:
    result, data = client.uid("search", None, *criteria)
    _ok(result, "Mail search failed")
    return (data[0] or b"").split()


def _load_messages(
    account: MailroomAccount, folder: str, limit: int, offset: int
) -> MessageListResponse:
    with _imap(account) as client:
        _select(client, folder)
        uids = _search_uids(client, "ALL")
        total = len(uids)
        newest_first = list(reversed(uids))
        page = newest_first[offset:offset + limit]
        return MessageListResponse(
            folder=folder,
            total=total,
            offset=offset,
            messages=_summaries(client, folder, page),
        )


def _search_messages(
    account: MailroomAccount, folder: str, query: str, limit: int
) -> MessageListResponse:
    # ponytail: a non-ASCII term rides in a quoted string rather than an IMAP
    # literal. Dovecot accepts it; switch to a literal if another server does not.
    term = query.replace("\\", "\\\\").replace('"', '\\"')
    with _imap(account) as client:
        _select(client, folder)
        uids = _search_uids(client, "CHARSET", "UTF-8", "TEXT", f'"{term}"'.encode())
        page = list(reversed(uids))[:limit]
        return MessageListResponse(
            folder=folder,
            total=len(uids),
            offset=0,
            messages=_summaries(client, folder, page),
        )


def _attachment_parts(parsed: Message) -> list[tuple[int, Message]]:
    parts: list[tuple[int, Message]] = []
    for index, part in enumerate(parsed.walk()):
        if part.get_content_maintype() == "multipart":
            continue
        parts.append((index, part))
    return parts


def _thread_neighbours(
    client: imaplib.IMAP4_SSL, folder: str, message_id: str | None
) -> list[ThreadNeighbour]:
    if not message_id:
        return []
    safe_id = message_id.replace('"', "")
    try:
        uids = _search_uids(
            client, "OR", "HEADER", "REFERENCES", f'"{safe_id}"',
            "HEADER", "IN-REPLY-TO", f'"{safe_id}"',
        )
    except HTTPException:
        return []
    page = list(reversed(uids))[:10]
    return [
        ThreadNeighbour(
            uid=summary.uid,
            subject=summary.subject,
            sender=summary.sender,
            date=summary.date,
        )
        for summary in _summaries(client, folder, page)
    ]


def _load_message(
    account: MailroomAccount, folder: str, uid: str, allow_remote: bool
) -> MessageResponse:
    with _imap(account) as client:
        _select(client, folder)
        result, rows = client.uid("fetch", uid.encode(), "(BODY.PEEK[])")
        if result != "OK" or not rows or not isinstance(rows[0], tuple):
            raise HTTPException(status_code=404, detail="Message not found")
        parsed = email.message_from_bytes(rows[0][1])

        inline: dict[str, str] = {}
        attachments: list[Attachment] = []
        for index, part in _attachment_parts(parsed):
            content_id = (part.get("Content-ID") or "").strip().strip("<>")
            payload = part.get_payload(decode=True) or b""
            if content_id:
                query = urlencode({"folder": folder, "account": account.email})
                inline[content_id] = (
                    f"/api/plugins/mailroom/messages/{uid}/attachments/{index}?{query}"
                )
            filename = _decode(part.get_filename())
            disposition = (part.get("Content-Disposition") or "").lower()
            is_body = not filename and not content_id and part.get_content_maintype() == "text"
            if is_body or (not filename and "attachment" not in disposition):
                continue
            attachments.append(Attachment(
                index=index,
                filename=filename or f"part-{index}",
                content_type=part.get_content_type(),
                size=len(payload),
            ))

        text = _plain_text(parsed)
        raw_html = _part_text(_body_part(parsed, "text/html"))
        html: str | None = None
        blocked = 0
        links: list[LinkTarget] = []
        if raw_html:
            html, blocked, links = _sanitize_html(raw_html, inline, allow_remote)
            if not text:
                text = _html_to_text(raw_html)

        message_id = (parsed.get("Message-ID") or "").strip() or None
        return MessageResponse(
            uid=uid,
            folder=folder,
            message_id=message_id,
            sender=_decode(parsed.get("From")),
            to=_decode(parsed.get("To")),
            cc=_decode(parsed.get("Cc")),
            subject=_decode(parsed.get("Subject")) or "(no subject)",
            date=_date(parsed.get("Date")),
            text=text,
            html=html,
            remote_images_blocked=blocked,
            links=links,
            attachments=attachments,
            thread=_thread_neighbours(client, folder, message_id),
        )


def _load_raw(account: MailroomAccount, folder: str, uid: str) -> bytes:
    with _imap(account) as client:
        _select(client, folder)
        result, rows = client.uid("fetch", uid.encode(), "(BODY.PEEK[])")
        if result != "OK" or not rows or not isinstance(rows[0], tuple):
            raise HTTPException(status_code=404, detail="Message not found")
        return rows[0][1]


def _load_attachment(
    account: MailroomAccount, folder: str, uid: str, index: int
) -> tuple[bytes, str, str]:
    parsed = email.message_from_bytes(_load_raw(account, folder, uid))
    for part_index, part in _attachment_parts(parsed):
        if part_index != index:
            continue
        return (
            part.get_payload(decode=True) or b"",
            part.get_content_type(),
            _decode(part.get_filename()) or f"part-{index}",
        )
    raise HTTPException(status_code=404, detail="Attachment not found")


def _set_flags(
    account: MailroomAccount, folder: str, uid: str, update: FlagUpdate
) -> None:
    with _imap(account) as client:
        _select(client, folder, readonly=False)
        for flag, wanted in (("\\Seen", update.seen), ("\\Flagged", update.flagged)):
            if wanted is None:
                continue
            result, _ = client.uid(
                "store", uid.encode(), "+FLAGS" if wanted else "-FLAGS", f"({flag})"
            )
            _ok(result, "Could not update that message")


def _ensure_folder(client: imaplib.IMAP4_SSL, folder: str) -> None:
    result, rows = client.list("", _quote(folder))
    if result == "OK" and any(isinstance(row, bytes) and row.strip() for row in rows or []):
        return
    client.create(_quote(folder))
    client.subscribe(_quote(folder))


def _move_message(
    account: MailroomAccount, folder: str, uid: str, destination: str
) -> None:
    with _imap(account) as client:
        _select(client, folder, readonly=False)
        _ensure_folder(client, destination)
        result, _ = client.uid("move", uid.encode(), _quote(destination))
        if result != "OK":
            # Older servers lack MOVE; copy then mark deleted and expunge.
            result, _ = client.uid("copy", uid.encode(), _quote(destination))
            _ok(result, "Could not move that message")
            client.uid("store", uid.encode(), "+FLAGS", "(\\Deleted)")
            client.expunge()


def _delete_message(account: MailroomAccount, folder: str, uid: str) -> None:
    trash = TRASH_FOLDER
    if folder.lower() == trash.lower():
        with _imap(account) as client:
            _select(client, folder, readonly=False)
            result, _ = client.uid("store", uid.encode(), "+FLAGS", "(\\Deleted)")
            _ok(result, "Could not delete that message")
            client.expunge()
        return
    _move_message(account, folder, uid, trash)


def _append(
    client: imaplib.IMAP4_SSL, folder: str, message: EmailMessage, flags: str = ""
) -> str | None:
    _ensure_folder(client, folder)
    result, data = client.append(
        _quote(folder), flags, imaplib.Time2Internaldate(datetime.now(timezone.utc)),
        message.as_bytes(),
    )
    if result != "OK":
        return None
    match = re.search(rb"APPENDUID \d+ (\d+)", (data[0] or b"") if data else b"")
    return match.group(1).decode("ascii") if match else None


# ---------------------------------------------------------------------------
# Unit 3: sender
# ---------------------------------------------------------------------------


def _recipients(*fields: str) -> list[str]:
    # An empty entry makes getaddresses treat the whole list as malformed and
    # return nothing, so blanks are dropped before parsing.
    populated = [field for field in fields if field and field.strip()]
    found = [address for _, address in getaddresses(populated) if "@" in address]
    return list(dict.fromkeys(found))


def _build(account: MailroomAccount, draft: Draft, message_id: str) -> EmailMessage:
    message = EmailMessage()
    message["From"] = formataddr((account.email.split("@")[0], account.email))
    if draft.to:
        message["To"] = draft.to
    if draft.cc:
        message["Cc"] = draft.cc
    message["Subject"] = draft.subject or "(no subject)"
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = message_id
    if draft.in_reply_to:
        message["In-Reply-To"] = draft.in_reply_to
    if draft.references:
        message["References"] = draft.references
    message.set_content(draft.body or "")
    return message


def _find_by_header(
    client: imaplib.IMAP4_SSL, folder: str, header: str, value: str
) -> str | None:
    try:
        _select(client, folder)
    except HTTPException:
        return None
    try:
        uids = _search_uids(client, "HEADER", header, f'"{value}"')
    except HTTPException:
        return None
    return uids[-1].decode("ascii") if uids else None


def _send(
    account: MailroomAccount, draft: Draft, idempotency_key: str | None
) -> SendResponse:
    settings = get_settings()
    to_addresses = _recipients(draft.to, draft.cc, draft.bcc)
    if not to_addresses:
        raise HTTPException(status_code=400, detail="Add at least one recipient")

    # The sent copy carries the key, so a retry is caught without mirroring
    # any mail into PostgreSQL.
    if idempotency_key:
        with _imap(account) as client:
            existing = _find_by_header(client, SENT_FOLDER, IDEMPOTENCY_HEADER, idempotency_key)
            if existing:
                return SendResponse(message_id=existing, duplicate=True)

    message_id = make_msgid(domain=settings.mailroom_domain)
    message = _build(account, draft, message_id)
    if idempotency_key:
        message[IDEMPOTENCY_HEADER] = idempotency_key

    try:
        with smtplib.SMTP(
            settings.smtp_host, settings.smtp_port, timeout=SMTP_TIMEOUT_SECONDS
        ) as server:
            server.starttls()
            server.login(account.email, account.password)
            server.sendmail(account.email, to_addresses, message.as_string())
    except smtplib.SMTPAuthenticationError:
        raise HTTPException(status_code=401, detail="Your mail password was rejected. Sign in again.")
    except (smtplib.SMTPException, OSError):
        raise HTTPException(status_code=502, detail="The message could not be sent. Try again.")

    with _imap(account) as client:
        _append(client, SENT_FOLDER, message, flags="(\\Seen)")
    return SendResponse(message_id=message_id, duplicate=False)


def _save_draft(account: MailroomAccount, request: SaveDraftRequest) -> SaveDraftResponse:
    message = _build(account, request, make_msgid(domain=get_settings().mailroom_domain))
    message[DRAFT_HEADER] = "1"
    with _imap(account) as client:
        if request.replaces_uid and request.replaces_uid.isdigit():
            _select(client, DRAFTS_FOLDER, readonly=False)
            client.uid("store", request.replaces_uid.encode(), "+FLAGS", "(\\Deleted)")
            client.expunge()
        return SaveDraftResponse(
            uid=_append(client, DRAFTS_FOLDER, message, flags="(\\Draft \\Seen)")
        )


def _send_otp_code(address: str, code: str) -> None:
    """Deliver the sign-in code through the existing outbound path."""
    settings = get_settings()
    if not (settings.smtp_host and settings.smtp_user and settings.smtp_pass):
        raise HTTPException(
            status_code=503, detail="Sign-in codes are not configured. Use your password."
        )
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = address
    message["Subject"] = f"{code} is your Mailroom sign-in code"
    message["Date"] = formatdate(localtime=True)
    message.set_content(
        f"Your Mailroom sign-in code is {code}.\n\n"
        f"It expires in {int(OTP_TTL.total_seconds() // 60)} minutes. "
        "If you did not ask for it, you can ignore this message."
    )
    with smtplib.SMTP(
        settings.smtp_host, settings.smtp_port, timeout=SMTP_TIMEOUT_SECONDS
    ) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_pass)
        server.sendmail(settings.smtp_user, [address], message.as_string())


# ---------------------------------------------------------------------------
# Unit 4: assistant
# ---------------------------------------------------------------------------

_ASSISTANT_PROMPTS = {
    "summarize": (
        "Summarize this email thread in at most four sentences. "
        'Reply with JSON: {"summary": "..."}'
    ),
    "reply": (
        "Write a reply to this thread following the instruction. "
        'Reply with JSON: {"body": "..."}'
    ),
    "rewrite": (
        "Rewrite the draft following the instruction. Keep the author's meaning. "
        'Reply with JSON: {"body": "..."}'
    ),
    "triage": (
        "Decide whether this thread should be archived, replied to, or kept. "
        'Reply with JSON: {"suggestion": "archive|reply|keep", "reason": "..."}'
    ),
}


def _json_completion(messages: list[dict[str, str]]) -> dict[str, Any]:
    raw = get_llm_client()._chat_completion(messages, json_response=True).strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].removesuffix("```").removeprefix("json\n").strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="The assistant returned an unusable answer")
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=502, detail="The assistant returned an unusable answer")
    return parsed


def _thread_context(account: MailroomAccount, folder: str, uid: str) -> str:
    """Only the thread the action is about, truncated. Nothing else is sent."""
    message = _load_message(account, folder, uid, allow_remote=False)
    blocks = [
        f"From: {message.sender}\nSubject: {message.subject}\n\n"
        f"{message.text[:ASSISTANT_CHARS_PER_MESSAGE]}"
    ]
    for neighbour in message.thread[: ASSISTANT_THREAD_MESSAGES - 1]:
        blocks.append(f"From: {neighbour.sender}\nSubject: {neighbour.subject}")
    return "\n\n---\n\n".join(blocks)


def _run_assistant(
    account: MailroomAccount,
    request: AssistantRequest,
    preferences: AiPreferences,
) -> AssistantResponse:
    context = ""
    if request.uid:
        context = _thread_context(account, request.folder, request.uid)
    if request.action == "rewrite" and not request.draft:
        raise HTTPException(status_code=400, detail="There is no draft to rewrite")
    if request.action in {"summarize", "triage"} and not context:
        raise HTTPException(status_code=400, detail="Open a message first")

    user_content = _ASSISTANT_PROMPTS[request.action]
    if context:
        user_content += f"\n\nThread:\n{context}"
    if request.draft:
        user_content += f"\n\nDraft:\n{request.draft[:ASSISTANT_CHARS_PER_MESSAGE]}"
    if request.instruction:
        user_content += f"\n\nInstruction:\n{request.instruction}"
    if request.action in {"reply", "rewrite"}:
        user_content += f"\n\nPreferred tone: {preferences.tone}."
        if preferences.signature:
            user_content += f"\nEnd with this signature:\n{preferences.signature}"

    parsed = _json_completion([
        {
            "role": "system",
            "content": (
                "You help someone read and write their own email. You never send, "
                "delete, or move mail. Respond with JSON only."
            ),
        },
        {"role": "user", "content": user_content},
    ])
    suggestion = str(parsed.get("suggestion") or "") or None
    if suggestion not in (None, "archive", "reply", "keep"):
        suggestion = "keep"
    return AssistantResponse(
        action=request.action,
        summary=str(parsed.get("summary") or "") or None,
        body=str(parsed.get("body") or "") or None,
        suggestion=suggestion,
        reason=str(parsed.get("reason") or "") or None,
    )


# ---------------------------------------------------------------------------
# Routes: session
# ---------------------------------------------------------------------------


@router.get("/session", response_model=SessionResponse)
async def get_session(db: DbSession, principal: CurrentUserDep) -> SessionResponse:
    account = await db.scalar(
        select(MailroomAccount).where(MailroomAccount.user_id == principal.user_id)
    )
    accounts = await _available_accounts(db, principal, account)
    return SessionResponse(
        authenticated=bool(accounts),
        email=account.email if account else (accounts[0] if accounts else None),
        accounts=accounts,
        preferences=_preferences(account),
    )


@router.post("/login", response_model=SessionResponse)
async def login(payload: LoginRequest, db: DbSession, principal: CurrentUserDep) -> SessionResponse:
    _check_domain(payload.email)
    try:
        await _in_worker(_verify_credentials, payload.email, payload.password)
    except (imaplib.IMAP4.error, OSError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="That email or password did not work")

    account = await db.scalar(
        select(MailroomAccount).where(MailroomAccount.user_id == principal.user_id)
    )
    if account is None:
        account = MailroomAccount(
            user_id=principal.user_id,
            email=payload.email,
            password=payload.password,
        )
        db.add(account)
    else:
        account.email = payload.email
        account.password = payload.password
        account.last_authenticated_at = datetime.now(timezone.utc)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That mailbox is already attached to another account",
        )
    accounts = await _available_accounts(db, principal, account)
    return SessionResponse(
        authenticated=True,
        email=payload.email,
        accounts=accounts,
        preferences=_preferences(account),
    )


@router.post("/otp/request", status_code=status.HTTP_202_ACCEPTED)
async def request_otp(payload: OtpRequest, db: DbSession) -> dict[str, str]:
    """Issue a sign-in code.

    The reply is identical whether or not the mailbox exists, so the endpoint
    cannot be used to enumerate addresses.
    """
    generic = {"detail": "If that mailbox can use a code, one is on its way."}
    account = await db.scalar(
        select(MailroomAccount).where(MailroomAccount.email == payload.email)
    )
    if account is None:
        return generic

    now = datetime.now(timezone.utc)
    challenge = await db.scalar(
        select(MailroomOtpChallenge).where(MailroomOtpChallenge.account_id == account.id)
    )
    if challenge is not None:
        created = challenge.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if now - created < OTP_RESEND_INTERVAL:
            raise HTTPException(status_code=429, detail="A code was just sent. Check your mailbox.")
        await db.delete(challenge)
        await db.flush()

    code = f"{secrets.randbelow(10 ** OTP_LENGTH):0{OTP_LENGTH}d}"
    db.add(MailroomOtpChallenge(
        account_id=account.id,
        code_hash=_hash_code(code),
        expires_at=now + OTP_TTL,
    ))
    await db.commit()
    try:
        await _in_worker(_send_otp_code, account.email, code)
    except (smtplib.SMTPException, OSError):
        raise HTTPException(status_code=502, detail="The code could not be sent. Try your password instead.")
    return generic


@router.post("/otp/verify", response_model=SessionResponse)
async def verify_otp(
    payload: OtpVerifyRequest, db: DbSession, principal: CurrentUserDep
) -> SessionResponse:
    rejected = HTTPException(status_code=401, detail="That code did not work")
    account = await db.scalar(
        select(MailroomAccount).where(MailroomAccount.email == payload.email)
    )
    if account is None or account.user_id != principal.user_id:
        raise rejected
    challenge = await db.scalar(
        select(MailroomOtpChallenge).where(MailroomOtpChallenge.account_id == account.id)
    )
    if challenge is None or challenge.consumed_at is not None:
        raise rejected

    now = datetime.now(timezone.utc)
    expires_at = challenge.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if now >= expires_at or challenge.attempts >= OTP_MAX_ATTEMPTS:
        await db.delete(challenge)
        await db.commit()
        raise rejected

    challenge.attempts += 1
    if not hmac.compare_digest(challenge.code_hash, _hash_code(payload.code)):
        await db.commit()
        raise rejected

    challenge.consumed_at = now
    account.last_authenticated_at = now
    await db.commit()
    accounts = await _available_accounts(db, principal, account)
    return SessionResponse(
        authenticated=True,
        email=account.email,
        accounts=accounts,
        preferences=_preferences(account),
    )


@router.delete("/session", response_model=SessionResponse)
async def logout(db: DbSession, principal: CurrentUserDep) -> SessionResponse:
    account = await db.scalar(
        select(MailroomAccount).where(MailroomAccount.user_id == principal.user_id)
    )
    if account is not None:
        await db.delete(account)
        await db.commit()
    accounts = await _available_accounts(db, principal, None)
    return SessionResponse(
        authenticated=bool(accounts),
        email=accounts[0] if accounts else None,
        accounts=accounts,
    )


@router.put("/preferences", response_model=AiPreferences)
async def update_preferences(
    payload: AiPreferences, db: DbSession, principal: CurrentUserDep
) -> AiPreferences:
    account = await db.scalar(
        select(MailroomAccount).where(MailroomAccount.user_id == principal.user_id)
    )
    if account is None:
        raise HTTPException(status_code=401, detail="Sign in to Mailroom")
    account.ai_preferences = payload.model_dump()
    await db.commit()
    return payload


# ---------------------------------------------------------------------------
# Routes: mailbox
# ---------------------------------------------------------------------------

MailFailure = (imaplib.IMAP4.error, OSError)


async def _mail(fn, *args):
    """Run a mail operation, turning protocol faults into a retryable 502."""
    try:
        return await _in_worker(fn, *args)
    except HTTPException:
        raise
    except imaplib.IMAP4.abort:
        raise HTTPException(status_code=502, detail="The mail server dropped the connection. Try again.")
    except MailFailure:
        raise HTTPException(status_code=502, detail="Mail server is unavailable")


@router.get("/folders", response_model=list[Folder])
async def folders(
    db: DbSession,
    principal: CurrentUserDep,
    account: str | None = Query(default=None, max_length=255),
) -> list[Folder]:
    return await _mail(_list_folders, await _selected_account(db, principal, account))


@router.get("/messages", response_model=MessageListResponse)
async def list_messages(
    db: DbSession,
    principal: CurrentUserDep,
    folder: str = Query(default="INBOX", max_length=80),
    account: str | None = Query(default=None, max_length=255),
    limit: int = Query(default=40, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10_000),
) -> MessageListResponse:
    _check_folder(folder)
    record = await _selected_account(db, principal, account)
    return await _mail(_load_messages, record, folder, limit, offset)


@router.get("/search", response_model=MessageListResponse)
async def search(
    db: DbSession,
    principal: CurrentUserDep,
    q: str = Query(min_length=2, max_length=200),
    folder: str = Query(default="INBOX", max_length=80),
    account: str | None = Query(default=None, max_length=255),
    limit: int = Query(default=40, ge=1, le=100),
) -> MessageListResponse:
    _check_folder(folder)
    record = await _selected_account(db, principal, account)
    return await _mail(_search_messages, record, folder, q, limit)


@router.get("/messages/{uid}", response_model=MessageResponse)
async def get_message(
    uid: str,
    db: DbSession,
    principal: CurrentUserDep,
    folder: str = Query(default="INBOX", max_length=80),
    account: str | None = Query(default=None, max_length=255),
    remote_images: bool = Query(default=False),
) -> MessageResponse:
    _check_uid(uid)
    _check_folder(folder)
    record = await _selected_account(db, principal, account)
    return await _mail(_load_message, record, folder, uid, remote_images)


@router.get("/messages/{uid}/raw")
async def get_raw_message(
    uid: str,
    db: DbSession,
    principal: CurrentUserDep,
    folder: str = Query(default="INBOX", max_length=80),
    account: str | None = Query(default=None, max_length=255),
) -> Response:
    _check_uid(uid)
    _check_folder(folder)
    record = await _selected_account(db, principal, account)
    raw = await _mail(_load_raw, record, folder, uid)
    return Response(
        content=raw,
        media_type="message/rfc822",
        headers={"Content-Disposition": f'attachment; filename="message-{uid}.eml"'},
    )


@router.get("/messages/{uid}/attachments/{index}")
async def get_attachment(
    uid: str,
    index: int,
    db: DbSession,
    principal: CurrentUserDep,
    folder: str = Query(default="INBOX", max_length=80),
    account: str | None = Query(default=None, max_length=255),
) -> Response:
    _check_uid(uid)
    _check_folder(folder)
    if index < 0 or index > 500:
        raise HTTPException(status_code=400, detail="Invalid attachment")
    record = await _selected_account(db, principal, account)
    payload, content_type, filename = await _mail(_load_attachment, record, folder, uid, index)
    # Images render inline so `cid:` references work. Everything else is an
    # opaque download, never a document that could run in the app's origin.
    is_image = content_type.startswith("image/") and "svg" not in content_type
    safe_name = re.sub(r'[^\w. -]', "_", filename)[:120] or f"part-{index}"
    return Response(
        content=payload,
        media_type=content_type if is_image else "application/octet-stream",
        headers={
            "Content-Disposition": (
                f'{"inline" if is_image else "attachment"}; filename="{safe_name}"'
            ),
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/messages/{uid}/flags", status_code=status.HTTP_204_NO_CONTENT)
async def update_flags(
    uid: str,
    payload: FlagUpdate,
    db: DbSession,
    principal: CurrentUserDep,
    folder: str = Query(default="INBOX", max_length=80),
    account: str | None = Query(default=None, max_length=255),
) -> None:
    _check_uid(uid)
    _check_folder(folder)
    record = await _selected_account(db, principal, account)
    await _mail(_set_flags, record, folder, uid, payload)


@router.post("/messages/{uid}/move", status_code=status.HTTP_204_NO_CONTENT)
async def move_message(
    uid: str,
    payload: MoveRequest,
    db: DbSession,
    principal: CurrentUserDep,
    folder: str = Query(default="INBOX", max_length=80),
    account: str | None = Query(default=None, max_length=255),
) -> None:
    _check_uid(uid)
    _check_folder(folder)
    _check_folder(payload.folder)
    record = await _selected_account(db, principal, account)
    await _mail(_move_message, record, folder, uid, payload.folder)


@router.post("/messages/{uid}/archive", status_code=status.HTTP_204_NO_CONTENT)
async def archive_message(
    uid: str,
    db: DbSession,
    principal: CurrentUserDep,
    folder: str = Query(default="INBOX", max_length=80),
    account: str | None = Query(default=None, max_length=255),
) -> None:
    _check_uid(uid)
    _check_folder(folder)
    record = await _selected_account(db, principal, account)
    await _mail(_move_message, record, folder, uid, ARCHIVE_FOLDER)


@router.delete("/messages/{uid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    uid: str,
    db: DbSession,
    principal: CurrentUserDep,
    folder: str = Query(default="INBOX", max_length=80),
    account: str | None = Query(default=None, max_length=255),
) -> None:
    _check_uid(uid)
    _check_folder(folder)
    record = await _selected_account(db, principal, account)
    await _mail(_delete_message, record, folder, uid)


def _check_uid(uid: str) -> None:
    if not uid.isdigit() or len(uid) > 20:
        raise HTTPException(status_code=400, detail="Invalid message")


# ---------------------------------------------------------------------------
# Routes: sending and the assistant
# ---------------------------------------------------------------------------


@router.post("/drafts", response_model=SaveDraftResponse)
async def save_draft(
    payload: SaveDraftRequest,
    db: DbSession,
    principal: CurrentUserDep,
    account: str | None = Query(default=None, max_length=255),
) -> SaveDraftResponse:
    record = await _selected_account(db, principal, account)
    return await _mail(_save_draft, record, payload)


@router.post("/messages", response_model=SendResponse)
async def send_message(
    payload: Draft,
    db: DbSession,
    principal: CurrentUserDep,
    account: str | None = Query(default=None, max_length=255),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> SendResponse:
    if idempotency_key and not SAFE_IDEMPOTENCY_KEY.fullmatch(idempotency_key):
        raise HTTPException(status_code=400, detail="Invalid idempotency key")
    record = await _selected_account(db, principal, account)
    return await _mail(_send, record, payload, idempotency_key)


@router.post("/assistant", response_model=AssistantResponse)
async def run_assistant(
    payload: AssistantRequest,
    db: DbSession,
    principal: CurrentUserDep,
    account: str | None = Query(default=None, max_length=255),
) -> AssistantResponse:
    _check_folder(payload.folder)
    if payload.uid:
        _check_uid(payload.uid)
    record = await _selected_account(db, principal, account)
    personal = await db.scalar(
        select(MailroomAccount).where(MailroomAccount.user_id == principal.user_id)
    )
    try:
        return await _in_worker(_run_assistant, record, payload, _preferences(personal))
    except HTTPException:
        raise
    except MailFailure:
        raise HTTPException(status_code=502, detail="Mail server is unavailable")
    except RuntimeError:
        raise HTTPException(status_code=502, detail="The assistant is unavailable right now")


def get_manifest() -> PluginManifest:
    return PluginManifest(
        id="mailroom",
        name="Mailroom",
        version="0.2.0",
        description="A small live webmail client for bits&bytes accounts.",
        router=router,
        ui_panels=[UiPanelDeclaration(
            id="mailroom",
            title="Mailroom",
            route_segment="inbox",
            placement="sidebar",
            icon="Mail",
        )],
    )
