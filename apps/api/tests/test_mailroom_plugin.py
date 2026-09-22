"""Mailroom's local parsing, safe rendering, and encrypted account boundary."""

import contextlib
import email
import importlib.util
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select

from app.config import get_settings
from app.db.models import (
    EncryptedString,
    Group,
    MailroomAccount,
    MailroomOtpChallenge,
    Membership,
    User,
)
from app.iam.principal import resolve_principal


REPO_ROOT = Path(__file__).resolve().parents[3]


def _mailroom():
    path = REPO_ROOT / "plugins" / "mailroom" / "api" / "main.py"
    name = "plugin_mailroom_tests"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _account(email_address: str = "me@gobitsnbytes.org") -> MailroomAccount:
    return MailroomAccount(user_id=uuid.uuid4(), email=email_address, password="x")


# ---------------------------------------------------------------------------
# MIME parsing
# ---------------------------------------------------------------------------


def test_mailroom_decodes_subject_and_plain_body():
    plugin = _mailroom()
    message = email.message_from_bytes(
        b"Subject: =?utf-8?b?SGVsbG8g4pyT?=\r\n"
        b"From: Aadrika <aadrika@gobitsnbytes.org>\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
        b"A short, real message."
    )

    assert plugin._decode(message["Subject"]) == "Hello ✓"
    assert plugin._plain_text(message) == "A short, real message."


def test_mailroom_ignores_plain_text_attachments():
    plugin = _mailroom()
    message = email.message_from_bytes(
        b"MIME-Version: 1.0\r\n"
        b"Content-Type: multipart/mixed; boundary=x\r\n\r\n"
        b"--x\r\nContent-Type: text/plain\r\nContent-Disposition: attachment\r\n\r\nsecret.txt\r\n"
        b"--x\r\nContent-Type: text/plain\r\n\r\nVisible body\r\n--x--\r\n"
    )

    assert plugin._plain_text(message).strip() == "Visible body"


def test_mailroom_falls_back_to_html_when_there_is_no_plain_part():
    plugin = _mailroom()
    message = email.message_from_bytes(
        b"MIME-Version: 1.0\r\n"
        b"Content-Type: text/html; charset=utf-8\r\n\r\n"
        b"<p>Only a formatted body</p>"
    )

    assert plugin._plain_text(message) == ""
    assert plugin._html_to_text("<p>Only a formatted body</p>") == "Only a formatted body"


# ---------------------------------------------------------------------------
# Safe rendering
# ---------------------------------------------------------------------------


def test_mailroom_sanitizer_drops_active_content():
    plugin = _mailroom()
    hostile = (
        '<p onclick="steal()">hi</p>'
        "<script>alert(1)</script>"
        "<style>body{background:url(http://evil/x)}</style>"
        '<iframe src="http://evil"></iframe>'
        '<form action="http://evil"><input name="p"></form>'
        '<a href="javascript:alert(1)">bad</a>'
        '<span style="position:fixed;color:red">float</span>'
    )

    html, _, _ = plugin._sanitize_html(hostile, {}, allow_remote=False)

    for forbidden in ("script", "iframe", "<form", "onclick", "javascript:", "position"):
        assert forbidden not in html
    assert "color:red" in html


def test_mailroom_blocks_remote_images_until_asked():
    plugin = _mailroom()
    body = '<img src="http://tracker.example/pixel.gif">'

    blocked_html, blocked, _ = plugin._sanitize_html(body, {}, allow_remote=False)
    loaded_html, still_blocked, _ = plugin._sanitize_html(body, {}, allow_remote=True)

    assert blocked == 1
    assert "tracker.example" not in blocked_html
    assert still_blocked == 0
    assert "tracker.example" in loaded_html


def test_mailroom_serves_inline_images_through_the_attachment_route():
    plugin = _mailroom()
    body = '<img src="cid:logo"><a href="cid:logo">x</a>'

    html, _, links = plugin._sanitize_html(body, {"logo": "/api/att/3"}, allow_remote=False)

    assert 'src="/api/att/3"' in html
    # A cid: reference is only ever an image source, never a link target.
    assert "cid:" not in html
    assert links == []


def test_mailroom_reports_real_link_destinations():
    plugin = _mailroom()

    _, _, links = plugin._sanitize_html(
        '<a href="https://real.example/path">Click here</a>', {}, allow_remote=False
    )

    assert [link.href for link in links] == ["https://real.example/path"]


# ---------------------------------------------------------------------------
# IMAP behaviour, against a fake protocol client
# ---------------------------------------------------------------------------


class FakeIMAP:
    """Enough of imaplib to exercise the mailbox and sender units."""

    def __init__(self, messages, search_results=None):
        self.messages = messages
        self.uids = list(messages)
        self.search_results = self.uids if search_results is None else search_results
        self.commands = []
        self.appended = []

    def select(self, folder, readonly=True):
        self.commands.append(("select", folder, readonly))
        return "OK", [str(len(self.uids)).encode()]

    def list(self, *args):
        return "OK", [b'(\\HasNoChildren) "." "INBOX"']

    def create(self, folder):
        return "OK", [b""]

    def subscribe(self, folder):
        return "OK", [b""]

    def append(self, folder, flags, date, message):
        self.appended.append((folder, message))
        return "OK", [b"[APPENDUID 1 99] done"]

    def expunge(self):
        return "OK", [b""]

    def uid(self, command, *args):
        self.commands.append((command.lower(),) + args)
        command = command.lower()
        if command == "search":
            return "OK", [b" ".join(self.search_results)]
        if command == "fetch":
            return "OK", self._fetch(args[0], args[1])
        return "OK", [b""]

    def _fetch(self, uid_set, spec):
        rows = []
        for uid in uid_set.split(b","):
            raw = self.messages.get(uid, b"")
            if spec == "(UID FLAGS)":
                rows.append(b"1 (UID " + uid + b" FLAGS (\\Seen))")
                continue
            if "HEADER.FIELDS" in spec:
                payload = raw.split(b"\r\n\r\n", 1)[0]
                label = b"BODY[HEADER.FIELDS]"
            elif "BODY.PEEK[1]" in spec:
                payload = raw.split(b"\r\n\r\n", 1)[-1]
                label = b"BODY[1]<0>"
            else:
                payload = raw
                label = b"BODY[]"
            rows.append((b"1 (UID " + uid + b" " + label, payload))
            rows.append(b")")
        return rows


def _message(subject, body="Body text"):
    return (
        "From: Someone <someone@gobitsnbytes.org>\r\n"
        "To: me@gobitsnbytes.org\r\n"
        f"Subject: {subject}\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        f"\r\n{body}"
    ).encode()


def _use_fake(plugin, monkeypatch, fake):
    @contextlib.contextmanager
    def fake_imap(account):
        yield fake

    monkeypatch.setattr(plugin, "_imap", fake_imap)


def test_mailroom_pages_newest_first(monkeypatch):
    plugin = _mailroom()
    messages = {str(index).encode(): _message(f"Message {index}") for index in range(1, 11)}
    fake = FakeIMAP(messages)
    _use_fake(plugin, monkeypatch, fake)

    first = plugin._load_messages(_account(), "INBOX", limit=3, offset=0)
    second = plugin._load_messages(_account(), "INBOX", limit=3, offset=3)

    assert first.total == 10
    assert [row.subject for row in first.messages] == ["Message 10", "Message 9", "Message 8"]
    assert [row.subject for row in second.messages] == ["Message 7", "Message 6", "Message 5"]
    assert second.offset == 3


def test_mailroom_reads_one_message_from_the_named_folder(monkeypatch):
    plugin = _mailroom()
    fake = FakeIMAP({b"7": _message("Hello", "A short, real message.")})
    _use_fake(plugin, monkeypatch, fake)

    message = plugin._load_message(_account(), "Archive", "7", allow_remote=False)

    assert message.subject == "Hello"
    assert message.text == "A short, real message."
    assert message.folder == "Archive"
    assert ("select", '"Archive"', True) in fake.commands


def test_mailroom_rejects_folder_names_that_could_escape_the_command():
    plugin = _mailroom()

    for hostile in ['INBOX" (\\Deleted', "IN\\BOX", "a" * 200, "INBOX\r\nLOGOUT"]:
        try:
            plugin._check_folder(hostile)
        except HTTPException as error:
            assert error.status_code == 400
        else:
            raise AssertionError(f"{hostile!r} should have been rejected")


# ---------------------------------------------------------------------------
# Send idempotency
# ---------------------------------------------------------------------------


def test_mailroom_send_retry_does_not_create_a_second_message(monkeypatch):
    plugin = _mailroom()
    # The Sent folder already holds a copy carrying this key.
    fake = FakeIMAP({b"4": _message("Already sent")}, search_results=[b"4"])
    _use_fake(plugin, monkeypatch, fake)

    def explode(*args, **kwargs):
        raise AssertionError("a duplicate send reached SMTP")

    monkeypatch.setattr(plugin.smtplib, "SMTP", explode)

    result = plugin._send(
        _account(),
        plugin.Draft(to="them@example.com", subject="Hi", body="Hello"),
        "retry-key-0001",
    )

    assert result.duplicate is True
    assert result.message_id == "4"


def test_mailroom_send_requires_a_recipient():
    plugin = _mailroom()

    try:
        plugin._send(_account(), plugin.Draft(subject="Hi", body="Hello"), None)
    except HTTPException as error:
        assert error.status_code == 400
    else:
        raise AssertionError("a message with no recipient should be refused")


def test_mailroom_rejects_an_unusable_idempotency_key():
    plugin = _mailroom()

    assert plugin.SAFE_IDEMPOTENCY_KEY.fullmatch("b7c1f0aa-2f3d-4a1b-9c8e-101112131415")
    assert not plugin.SAFE_IDEMPOTENCY_KEY.fullmatch('key" HEADER X')
    assert not plugin.SAFE_IDEMPOTENCY_KEY.fullmatch("short")


# ---------------------------------------------------------------------------
# Accounts and mailbox isolation
# ---------------------------------------------------------------------------


def test_mailroom_account_password_uses_encrypted_column():
    assert isinstance(MailroomAccount.__table__.c.password.type, EncryptedString)


def test_mailroom_manifest_is_auth_only_and_user_facing():
    manifest = _mailroom().get_manifest()

    assert manifest.id == "mailroom"
    assert manifest.ui_panels[0].required_permission is None


async def test_executive_can_open_configured_hello_mailbox(db_session, monkeypatch):
    plugin = _mailroom()
    monkeypatch.setenv("MAILROOM_HELLO_PASSWORD", "shared-test-password")
    get_settings.cache_clear()
    user = User(display_name="Executive", is_super_admin=False)
    group = Group(id=uuid.uuid4(), name="Executive Leadership", slug="sg_executive")
    db_session.add_all([user, group])
    await db_session.flush()
    db_session.add(Membership(user_id=user.id, group_id=group.id, source="manual"))
    await db_session.commit()

    principal = await resolve_principal(db_session, user.id)
    accounts = await plugin._available_accounts(db_session, principal, None)

    assert accounts == ["hello@gobitsnbytes.org"]


async def test_regular_user_cannot_open_shared_mailbox(db_session, monkeypatch):
    plugin = _mailroom()
    monkeypatch.setenv("MAILROOM_HELLO_PASSWORD", "shared-test-password")
    get_settings.cache_clear()
    user = User(display_name="Member", is_super_admin=False)
    db_session.add(user)
    await db_session.commit()

    principal = await resolve_principal(db_session, user.id)

    assert await plugin._available_accounts(db_session, principal, None) == []


async def test_regular_user_cannot_name_someone_elses_mailbox(db_session):
    plugin = _mailroom()
    owner = User(display_name="Owner", is_super_admin=False)
    other = User(display_name="Other", is_super_admin=False)
    db_session.add_all([owner, other])
    await db_session.flush()
    db_session.add(MailroomAccount(
        user_id=owner.id, email="owner@gobitsnbytes.org", password="secret"
    ))
    await db_session.commit()
    principal = await resolve_principal(db_session, other.id)

    try:
        await plugin._selected_account(db_session, principal, "owner@gobitsnbytes.org")
    except HTTPException as error:
        assert error.status_code in (401, 403)
    else:
        raise AssertionError("one identity must not reach another's mailbox")


# ---------------------------------------------------------------------------
# Sign-in codes
# ---------------------------------------------------------------------------


async def _signed_in(db_session, email_address):
    user = User(display_name="Coder", is_super_admin=False)
    db_session.add(user)
    await db_session.flush()
    account = MailroomAccount(
        user_id=user.id, email=email_address, password="mailbox-password"
    )
    db_session.add(account)
    await db_session.commit()
    return user, account


async def _challenge(db_session, account, code, ttl=timedelta(minutes=5)):
    plugin = _mailroom()
    db_session.add(MailroomOtpChallenge(
        account_id=account.id,
        code_hash=plugin._hash_code(code),
        expires_at=datetime.now(timezone.utc) + ttl,
    ))
    await db_session.commit()


async def test_mailroom_otp_is_stored_only_as_a_keyed_digest(db_session, monkeypatch):
    plugin = _mailroom()
    _, account = await _signed_in(db_session, "digest@gobitsnbytes.org")
    sent = []
    monkeypatch.setattr(
        plugin, "_send_otp_code", lambda address, code: sent.append((address, code))
    )

    await plugin.request_otp(plugin.OtpRequest(email=account.email), db_session)

    challenge = await db_session.scalar(
        select(MailroomOtpChallenge).where(MailroomOtpChallenge.account_id == account.id)
    )
    code = sent[0][1]
    assert len(code) == plugin.OTP_LENGTH and code.isdigit()
    assert challenge.code_hash != code
    assert challenge.code_hash == plugin._hash_code(code)


async def test_mailroom_otp_does_not_reveal_unknown_mailboxes(db_session, monkeypatch):
    plugin = _mailroom()
    monkeypatch.setattr(plugin, "_send_otp_code", lambda address, code: None)

    answer = await plugin.request_otp(
        plugin.OtpRequest(email="nobody@gobitsnbytes.org"), db_session
    )

    assert "on its way" in answer["detail"]


async def test_mailroom_otp_rejects_an_expired_code(db_session):
    plugin = _mailroom()
    user, account = await _signed_in(db_session, "expired@gobitsnbytes.org")
    await _challenge(db_session, account, "123456", ttl=timedelta(minutes=-1))
    principal = await resolve_principal(db_session, user.id)

    try:
        await plugin.verify_otp(
            plugin.OtpVerifyRequest(email=account.email, code="123456"),
            db_session,
            principal,
        )
    except HTTPException as error:
        assert error.status_code == 401
    else:
        raise AssertionError("an expired code should not sign anyone in")


async def test_mailroom_otp_stops_after_the_attempt_limit(db_session):
    plugin = _mailroom()
    user, account = await _signed_in(db_session, "guessed@gobitsnbytes.org")
    await _challenge(db_session, account, "123456")
    principal = await resolve_principal(db_session, user.id)

    for _ in range(plugin.OTP_MAX_ATTEMPTS):
        try:
            await plugin.verify_otp(
                plugin.OtpVerifyRequest(email=account.email, code="000000"),
                db_session,
                principal,
            )
        except HTTPException:
            pass

    try:
        await plugin.verify_otp(
            plugin.OtpVerifyRequest(email=account.email, code="123456"),
            db_session,
            principal,
        )
    except HTTPException as error:
        assert error.status_code == 401
    else:
        raise AssertionError("the real code must stop working once attempts run out")


async def test_mailroom_otp_works_once_and_only_once(db_session):
    plugin = _mailroom()
    user, account = await _signed_in(db_session, "verified@gobitsnbytes.org")
    await _challenge(db_session, account, "654321")
    principal = await resolve_principal(db_session, user.id)

    session = await plugin.verify_otp(
        plugin.OtpVerifyRequest(email=account.email, code="654321"), db_session, principal
    )
    assert session.authenticated is True

    try:
        await plugin.verify_otp(
            plugin.OtpVerifyRequest(email=account.email, code="654321"),
            db_session,
            principal,
        )
    except HTTPException as error:
        assert error.status_code == 401
    else:
        raise AssertionError("a consumed code should not work twice")


async def test_mailroom_otp_belongs_to_one_identity(db_session):
    plugin = _mailroom()
    _, account = await _signed_in(db_session, "owner2@gobitsnbytes.org")
    await _challenge(db_session, account, "111111")
    intruder = User(display_name="Intruder", is_super_admin=False)
    db_session.add(intruder)
    await db_session.commit()
    principal = await resolve_principal(db_session, intruder.id)

    try:
        await plugin.verify_otp(
            plugin.OtpVerifyRequest(email=account.email, code="111111"),
            db_session,
            principal,
        )
    except HTTPException as error:
        assert error.status_code == 401
    else:
        raise AssertionError("a code must not sign in a different identity")


async def test_mailroom_otp_throttles_resends(db_session, monkeypatch):
    plugin = _mailroom()
    _, account = await _signed_in(db_session, "resend@gobitsnbytes.org")
    monkeypatch.setattr(plugin, "_send_otp_code", lambda address, code: None)

    await plugin.request_otp(plugin.OtpRequest(email=account.email), db_session)
    try:
        await plugin.request_otp(plugin.OtpRequest(email=account.email), db_session)
    except HTTPException as error:
        assert error.status_code == 429
    else:
        raise AssertionError("a second code within the window should be refused")


# ---------------------------------------------------------------------------
# Privacy
# ---------------------------------------------------------------------------


def test_mailroom_tables_hold_no_mail_content():
    mail_content = {
        "subject", "sender", "recipient", "recipients", "snippet", "body",
        "html", "text", "attachment", "attachments", "message", "transcript",
        "headers", "preview",
    }
    for table in (MailroomAccount.__table__, MailroomOtpChallenge.__table__):
        overlap = {column.name for column in table.columns} & mail_content
        assert not overlap, f"{table.name} would store mail content: {sorted(overlap)}"
