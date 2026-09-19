"""
Tests for the Legal Agent service: MIME parsing, inbox dedupe + polling,
signature-nudge sequencing, RAG /ask over executed contracts, agent stats.
"""

import uuid
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.services.legal_agent as legal_agent
from app.config import get_settings
from app.db.models import (
    AuditLog,
    ContractAssistantClause,
    ContractAssistantContract,
    ContractAssistantEnvelope,
    ContractAssistantEvent,
    SignatureAuditLog,
    SignatureRecipient,
    SignatureRequest,
)
from app.main import app
from app.database import get_session
from app.services.llm_client import SparkCloudAIClient
from app.db.models import User
from conftest import request_as


pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture(autouse=True)
async def override_db():
    """Fresh engine per test.

    pytest-asyncio runs each test on its own event loop while conftest's shared
    engine pools aiosqlite connections across loops; reusing a pooled
    connection on a dead loop intermittently serves stale reads. A per-test
    engine guarantees every connection lives on the active loop and is fully
    disposed afterwards.
    """
    engine = create_async_engine(os.environ["DATABASE_URL"])
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def _get_test_session():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_session] = _get_test_session
    yield session_maker
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(override_db):
    async with override_db() as session:
        yield session
        await session.rollback()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_mime(message_id: str = "<test-mid-1@vendor.example>", attach: bool = True) -> bytes:
    msg = EmailMessage()
    msg["From"] = "Counsel Perry <counsel@vendor.example>"
    msg["To"] = "legal@gobitsnbytes.org"
    msg["Subject"] = "Vendor Agreement for review"
    msg["Message-ID"] = message_id
    msg.set_content("Please find the contract attached for your review.")
    if attach:
        msg.add_attachment(
            b"%PDF-1.4 fake-bytes",
            maintype="application",
            subtype="pdf",
            filename="vendor-agreement.pdf",
        )
        msg.add_attachment(
            b"PK\x03\x04docx-bytes",
            maintype="application",
            subtype="octet-stream",
            filename="annexure.docx",
        )
    return msg.as_bytes()


async def _seed_pending_nudge_scenario(db_session: AsyncSession, *, stale_days: int):
    """Pending request linked via envelope, single pending signatory."""
    now = datetime.now(timezone.utc)
    contract = ContractAssistantContract(
        title="Nudge Deal",
        status="out_for_signature",
        original_file_path="p.pdf",
    )
    db_session.add(contract)
    await db_session.flush()

    request = SignatureRequest(
        title="Nudge Deal Agreement",
        status="pending",
        original_file_path="p.pdf",
        created_at=now - timedelta(days=stale_days + 1),
    )
    db_session.add(request)
    await db_session.flush()

    recipient = SignatureRecipient(
        request_id=request.id,
        name="Ria Signatory",
        email="ria@signer.example",
        access_token="nudge_tok_123",
        status="pending",
    )
    db_session.add(recipient)
    await db_session.flush()  # materialize recipient.id (column default)

    envelope = ContractAssistantEnvelope(
        contract_id=contract.id,
        signature_request_id=request.id,
        status="pending",
    )
    db_session.add(envelope)

    db_session.add(
        SignatureAuditLog(
            request_id=request.id,
            recipient_id=recipient.id,
            action="viewed",
            created_at=now - timedelta(days=stale_days),
        )
    )
    await db_session.commit()
    return contract, request, recipient


# ---------------------------------------------------------------------------
# parse_message
# ---------------------------------------------------------------------------

async def test_parse_message_extracts_attachments_and_bodies():
    raw = _build_mime()
    parsed = legal_agent.parse_message(raw)

    assert parsed.from_addr == "counsel@vendor.example"
    assert parsed.subject == "Vendor Agreement for review"
    assert parsed.message_id == "<test-mid-1@vendor.example>"
    assert "contract attached" in parsed.body_text
    assert parsed.received_at.tzinfo is not None

    names = [a[0] for a in parsed.attachments]
    assert "vendor-agreement.pdf" in names
    assert "annexure.docx" in names

    by_name = {a[0]: a for a in parsed.attachments}
    assert by_name["vendor-agreement.pdf"][1] == "application/pdf"
    assert by_name["annexure.docx"][1] == "application/octet-stream"
    assert by_name["vendor-agreement.pdf"][2].startswith(b"%PDF")


async def test_parse_message_without_attachments_is_clean():
    parsed = legal_agent.parse_message(_build_mime(attach=False))
    assert parsed.attachments == []
    assert "review" in parsed.body_text


async def test_internal_plain_email_receives_policy_reply(db_session, monkeypatch):
    raw = _build_mime(attach=False).replace(
        b"counsel@vendor.example", b"member@gobitsnbytes.org"
    )
    message = legal_agent.parse_message(raw)
    sent = {}

    def fake_reply(*args, **kwargs):
        sent["body"] = args[3]
        return True

    monkeypatch.setattr(legal_agent, "send_reply", fake_reply)
    handled = await legal_agent.handle_inbox_message(db_session, get_settings(), message)

    assert handled is True
    assert "policy" in sent["body"].lower()


# ---------------------------------------------------------------------------
# Dedupe
# ---------------------------------------------------------------------------

async def test_dedupe_skips_known_message_id(db_session: AsyncSession):
    db_session.add(
        ContractAssistantContract(
            title="Already ingested",
            original_file_path="x.pdf",
            message_id="<dup-1@vendor.example>",
        )
    )
    await db_session.commit()

    assert await legal_agent.is_duplicate_inbound(db_session, "<dup-1@vendor.example>") is True
    assert await legal_agent.is_duplicate_inbound(db_session, "<fresh-1@vendor.example>") is False


async def test_dedupe_falls_back_to_event_payload_scan(db_session: AsyncSession):
    contract = ContractAssistantContract(title="Payload only", original_file_path="y.pdf")
    db_session.add(contract)
    await db_session.flush()
    db_session.add(
        ContractAssistantEvent(
            contract_id=contract.id,
            type=legal_agent.INBOUND_EVENT_TYPE,
            payload={"message_id": "<dup-2@vendor.example>"},
        )
    )
    await db_session.commit()

    assert await legal_agent.is_duplicate_inbound(db_session, "<dup-2@vendor.example>") is True


async def test_handle_message_short_circuits_on_duplicate(db_session: AsyncSession, monkeypatch):
    db_session.add(
        ContractAssistantContract(
            title="Original ingest",
            original_file_path="o.pdf",
            message_id="<dup-mail@vendor.example>",
        )
    )
    await db_session.commit()

    called = {"reply": 0}

    def fake_reply(*args, **kwargs):
        called["reply"] += 1
        return True

    monkeypatch.setattr(legal_agent, "send_reply", fake_reply)

    before = len((await db_session.execute(select(ContractAssistantContract))).scalars().all())
    message = legal_agent.parse_message(_build_mime("<dup-mail@vendor.example>"))
    handled = await legal_agent.handle_inbox_message(db_session, get_settings(), message)

    assert handled is True
    after = len((await db_session.execute(select(ContractAssistantContract))).scalars().all())
    assert after == before
    assert called["reply"] == 0


# ---------------------------------------------------------------------------
# Poller against mocked imaplib
# ---------------------------------------------------------------------------

class _FakeIMAP:
    instances: list = []

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.stored_flags = []
        _FakeIMAP.instances.append(self)

    def login(self, user, password):
        self.user = user

    def select(self, mailbox):
        return ("OK", [b"1"])

    def search(self, charset, *criteria):
        return ("OK", [b"1"])

    def fetch(self, num, spec):
        return ("OK", [(b"1", self.raw_payload)])

    def store(self, num, operation, flags):
        self.stored_flags.append((num, flags))

    def logout(self):
        pass


async def test_poll_once_marks_seen_and_dedupes(monkeypatch, db_session):
    monkeypatch.setenv("LEGAL_INBOX_IMAP_HOST", "imap.test.local")
    monkeypatch.setenv("LEGAL_INBOX_IMAP_USER", "legal@test.local")
    monkeypatch.setenv("LEGAL_INBOX_IMAP_PASSWORD", "not-a-secret")

    db_session.add(
        ContractAssistantContract(
            title="Prior ingest",
            original_file_path="z.pdf",
            message_id="<poll-dup@vendor.example>",
        )
    )
    await db_session.commit()

    _FakeIMAP.instances = []
    _FakeIMAP.raw_payload = _build_mime("<poll-dup@vendor.example>")
    monkeypatch.setattr(legal_agent.imaplib, "IMAP4_SSL", _FakeIMAP)

    poller = legal_agent.LegalInboxPoller(get_settings())
    processed = await poller.poll_once(db_session)

    assert processed == 1
    assert _FakeIMAP.instances, "IMAP connection was never opened"
    # The poller uses one connection for fetch and a separate one for \Seen.
    seen_markers = [inst for inst in _FakeIMAP.instances if inst.stored_flags]
    assert len(seen_markers) == 1
    assert seen_markers[0].stored_flags == [(b"1", "\\Seen")]

    total = len((await db_session.execute(select(ContractAssistantContract))).scalars().all())
    titles = [c.title for c in (await db_session.execute(select(ContractAssistantContract))).scalars().all()]
    assert total == 1 and titles == ["Prior ingest"]
    assert legal_agent.get_last_poll_at() is not None


async def test_poll_once_skips_when_unconfigured(monkeypatch, db_session):
    monkeypatch.delenv("LEGAL_INBOX_IMAP_HOST", raising=False)
    monkeypatch.delenv("LEGAL_INBOX_IMAP_USER", raising=False)
    monkeypatch.delenv("LEGAL_INBOX_IMAP_PASSWORD", raising=False)

    poller = legal_agent.LegalInboxPoller(get_settings())
    assert await poller.poll_once(db_session) == 0


async def test_poll_once_handles_empty_search_result(monkeypatch, db_session):
    monkeypatch.setenv("LEGAL_INBOX_IMAP_HOST", "imap.test.local")
    monkeypatch.setenv("LEGAL_INBOX_IMAP_USER", "legal@test.local")
    monkeypatch.setenv("LEGAL_INBOX_IMAP_PASSWORD", "not-a-secret")

    class _EmptyIMAP(_FakeIMAP):
        fetched_nums: list = []
        def search(self, charset, *criteria):
            return ("OK", [b""])
        def fetch(self, num, spec):
            self.fetched_nums.append(num)
            return ("OK", [(num, b"")])

    _EmptyIMAP.instances = []
    _EmptyIMAP.fetched_nums = []
    monkeypatch.setattr(legal_agent.imaplib, "IMAP4_SSL", _EmptyIMAP)

    poller = legal_agent.LegalInboxPoller(get_settings())
    processed = await poller.poll_once(db_session)
    assert processed == 0
    assert len(_EmptyIMAP.fetched_nums) == 0, "fetch must not be called when search returns empty"


async def test_poll_once_handles_space_separated_ids(monkeypatch, db_session):
    monkeypatch.setenv("LEGAL_INBOX_IMAP_HOST", "imap.test.local")
    monkeypatch.setenv("LEGAL_INBOX_IMAP_USER", "legal@test.local")
    monkeypatch.setenv("LEGAL_INBOX_IMAP_PASSWORD", "not-a-secret")

    def fake_reply(*args, **kwargs):
        return True
    monkeypatch.setattr(legal_agent, "send_reply", fake_reply)

    class _MultiIMAP(_FakeIMAP):
        fetched_nums: list = []
        def search(self, charset, *criteria):
            return ("OK", [b"10 20"])
        def fetch(self, num, spec):
            self.fetched_nums.append(num)
            raw = _build_mime(f"<multi-{num.decode()}@vendor.example>", attach=False).replace(
                b"counsel@vendor.example", b"member@gobitsnbytes.org"
            )
            return ("OK", [(num, raw)])

    _MultiIMAP.instances = []
    _MultiIMAP.fetched_nums = []
    monkeypatch.setattr(legal_agent.imaplib, "IMAP4_SSL", _MultiIMAP)

    poller = legal_agent.LegalInboxPoller(get_settings())
    processed = await poller.poll_once(db_session)
    assert processed == 2
    assert _MultiIMAP.fetched_nums == [b"10", b"20"]


# ---------------------------------------------------------------------------
# Nudge sequencer
# ---------------------------------------------------------------------------

async def test_nudge_selection_cadence_and_cap(db_session: AsyncSession):
    _, _, _ = await _seed_pending_nudge_scenario(db_session, stale_days=5)

    targets = await legal_agent.collect_nudge_targets(db_session)
    assert len(targets) == 1
    assert targets[0].cadence_day == 3
    assert targets[0].access_token == "nudge_tok_123"

    # After the day-3 reminder is recorded, an 8-day-stale signer moves to the 7d tier.
    recipient = targets[0]
    db_session.add(
        ContractAssistantEvent(
            contract_id=recipient.contract_id,
            type=legal_agent.REMINDER_EVENT_TYPE,
            payload={"recipient_id": str(recipient.recipient_id), "cadence_day": 3},
        )
    )
    audit_rows = (
        (await db_session.execute(select(SignatureAuditLog))).scalars().all()
    )
    for audit in audit_rows:
        audit.created_at = datetime.now(timezone.utc) - timedelta(days=8)
    await db_session.commit()

    targets = await legal_agent.collect_nudge_targets(db_session)
    assert len(targets) == 1
    assert targets[0].cadence_day == 7

    # Recording 7d + 14d reaches the cap of 3 nudges per recipient.
    for day in (7, 14):
        db_session.add(
            ContractAssistantEvent(
                contract_id=targets[0].contract_id,
                type=legal_agent.REMINDER_EVENT_TYPE,
                payload={"recipient_id": str(targets[0].recipient_id), "cadence_day": day},
            )
        )
    await db_session.commit()

    assert await legal_agent.collect_nudge_targets(db_session) == []


async def test_nudges_stop_after_completion_and_skip_unlinked(db_session: AsyncSession):
    contract, request, _ = await _seed_pending_nudge_scenario(db_session, stale_days=10)

    # Unlinked pending request must be skipped gracefully.
    orphan = SignatureRequest(
        title="No Envelope Request",
        status="pending",
        original_file_path="q.pdf",
        created_at=datetime.now(timezone.utc) - timedelta(days=20),
    )
    db_session.add(orphan)
    await db_session.flush()
    db_session.add(
        SignatureRecipient(
            request_id=orphan.id,
            name="Orphan Signer",
            email="orphan@signer.example",
            access_token="orphan_tok",
            status="pending",
        )
    )
    await db_session.commit()

    assert len(await legal_agent.collect_nudge_targets(db_session)) == 1

    request.status = "completed"
    await db_session.commit()

    targets = await legal_agent.collect_nudge_targets(db_session)
    assert all(t.request_id != request.id for t in targets)


async def test_signed_recipient_never_nudged(db_session: AsyncSession):
    _, request, recipient = await _seed_pending_nudge_scenario(db_session, stale_days=10)
    recipient.status = "signed"
    await db_session.commit()

    assert await legal_agent.collect_nudge_targets(db_session) == []


async def test_send_signature_nudge_persists_events_and_audit(db_session: AsyncSession, monkeypatch):
    contract = ContractAssistantContract(title="Send Target", original_file_path="s.pdf")
    db_session.add(contract)
    await db_session.flush()

    sent = {}

    def fake_smtp(settings_obj, to_emails, subject, html_body, *args, **kwargs):
        sent["to"] = list(to_emails)
        sent["subject"] = subject

    monkeypatch.setattr("app.routers.meetings.send_smtp_email", fake_smtp)

    target = legal_agent.NudgeTarget(
        request_id=uuid.uuid4(),
        recipient_id=uuid.uuid4(),
        contract_id=contract.id,
        title="Send Target Agreement",
        name="Nia",
        email="nia@signer.example",
        access_token="tok_abc",
        cadence_day=3,
        staleness_days=4,
    )

    assert await legal_agent.send_signature_nudge(db_session, target) is True
    assert sent["to"] == ["nia@signer.example"]
    assert "Send Target Agreement" in sent["subject"]

    reminder_events = (
        (await db_session.execute(select(ContractAssistantEvent)))
        .scalars().all()
    )
    reminders = [e for e in reminder_events if e.type == legal_agent.REMINDER_EVENT_TYPE]
    assert len(reminders) == 1
    assert reminders[0].payload["cadence_day"] == 3

    audits = (
        (
            await db_session.execute(
                select(AuditLog).where(AuditLog.action == "signature.reminder_sent")
            )
        )
        .scalars()
        .all()
    )
    assert len(audits) == 1
    assert audits[0].metadata_json["cadence_day"] == 3


# ---------------------------------------------------------------------------
# /ask RAG over OKF rules + executed contracts
# ---------------------------------------------------------------------------

async def test_ask_includes_executed_contract_hit(db_session: AsyncSession, monkeypatch):
    captured = {}

    def fake_chat_completion(self, messages, json_response=False):
        captured["context"] = messages[-1]["content"]
        return "Per the executed agreement, liability is capped at fees paid [Executed Contract: Master Services Agreement]."

    monkeypatch.setattr(SparkCloudAIClient, "_chat_completion", fake_chat_completion)

    user = User(display_name="Legal Member", email="member@gobitsnbytes.org")
    db_session.add(user)
    contract = ContractAssistantContract(
        title="Master Services Agreement",
        status="dotted",
        original_file_path="msa.pdf",
    )
    db_session.add(contract)
    await db_session.flush()
    db_session.add(
        ContractAssistantClause(
            contract_id=contract.id,
            ref="§8.1",
            heading="Limitation of Liability",
            text="Aggregate liability of either party shall not exceed the fees paid hereunder.",
            page_number=1,
        )
    )
    sig_req = SignatureRequest(
        title="Master Services Agreement",
        status="completed",
        original_file_path="msa.pdf",
    )
    db_session.add(sig_req)
    await db_session.flush()
    db_session.add(
        ContractAssistantEnvelope(
            contract_id=contract.id,
            signature_request_id=sig_req.id,
            status="completed",
        )
    )
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await request_as(
            client, user.id, "POST", "/api/contract-assistant/ask",
            json={"question": "What is the liability cap in the Master Services Agreement?"},
        )
        assert response.status_code == 200
        data = response.json()

    assert "fees paid" in data["answer"]
    labels_titles = {(s["label"], s["title"]) for s in data["sources"]}
    assert ("Executed Contract", "Master Services Agreement") in labels_titles, (
        f"sources={labels_titles} answer={data['answer'][:160]}"
    )
    assert "Limitation of Liability" in captured["context"]


async def test_ask_returns_empty_sources_when_no_match(db_session: AsyncSession, monkeypatch):
    def fail_completion(self, messages, json_response=False):
        raise AssertionError("LLM should not be called with an empty corpus match")

    monkeypatch.setattr(SparkCloudAIClient, "_chat_completion", fail_completion)

    user = User(display_name="Legal Member", email="member@gobitsnbytes.org")
    db_session.add(user)
    await db_session.commit()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await request_as(
            client, user.id, "POST", "/api/contract-assistant/ask",
            json={"question": "zzzzqqqq unrelated gibberish xyzzy"},
        )
        assert response.status_code == 200
        data = response.json()
    assert data["sources"] == []


async def test_ask_rejects_non_organization_account(db_session: AsyncSession):
    user = User(display_name="External", email="external@example.org")
    db_session.add(user)
    await db_session.commit()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await request_as(
            client, user.id, "POST", "/api/contract-assistant/ask",
            json={"question": "What is the liability cap?"},
        )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Agent stats
# ---------------------------------------------------------------------------

async def test_agent_stats_endpoint_shape(db_session: AsyncSession):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/contract-assistant/agent/stats")
        assert response.status_code == 200
        data = response.json()

    for key in (
        "inbox_processed_24h",
        "contracts_in_review",
        "out_for_signature",
        "dotted_count",
        "pending_nudges",
        "last_poll_at",
    ):
        assert key in data


# ---------------------------------------------------------------------------
# Loop prevention & Policy email formatting
# ---------------------------------------------------------------------------

async def test_handle_inbox_message_drops_self_email(db_session, monkeypatch):
    raw = _build_mime(attach=False).replace(
        b"counsel@vendor.example", b"legal@gobitsnbytes.org"
    )
    message = legal_agent.parse_message(raw)
    replied = []

    monkeypatch.setattr(legal_agent, "send_reply", lambda *args, **kwargs: replied.append(args))
    handled = await legal_agent.handle_inbox_message(db_session, get_settings(), message)

    assert handled is True
    assert len(replied) == 0, "Should never reply to self"


async def test_handle_inbox_message_drops_automated_bounces(db_session, monkeypatch):
    raw = _build_mime(attach=False).replace(
        b"counsel@vendor.example", b"MAILER-DAEMON@gobitsnbytes.org"
    ).replace(
        b"Vendor Agreement for review", b"Undelivered Mail Returned to Sender"
    )
    message = legal_agent.parse_message(raw)
    replied = []

    monkeypatch.setattr(legal_agent, "send_reply", lambda *args, **kwargs: replied.append(args))
    handled = await legal_agent.handle_inbox_message(db_session, get_settings(), message)

    assert handled is True
    assert len(replied) == 0, "Should never reply to delivery failure bounces"


async def test_handle_inbox_message_synthesizes_with_llm_and_formats_html(db_session, monkeypatch):
    raw = _build_mime(attach=False).replace(
        b"counsel@vendor.example", b"akshat@gobitsnbytes.org"
    )
    message = legal_agent.parse_message(raw)
    sent_replies = []

    def fake_reply(settings, to_addr, subject, text_body, html_body, in_reply_to, references):
        sent_replies.append({
            "to": to_addr,
            "subject": subject,
            "text": text_body,
            "html": html_body,
        })
        return True

    def fake_llm(self, messages, json_response=False):
        return "Per Foundation policy, sponsorships must be approved through official banking accounts [Sponsorships & Financial Limits]."

    monkeypatch.setattr(legal_agent, "send_reply", fake_reply)
    monkeypatch.setattr(SparkCloudAIClient, "_chat_completion", fake_llm)

    handled = await legal_agent.handle_inbox_message(db_session, get_settings(), message)

    assert handled is True
    assert len(sent_replies) == 1
    reply = sent_replies[0]
    assert reply["to"] == "akshat@gobitsnbytes.org"
    assert "sponsorships must be approved" in reply["text"].lower()
    assert "<pre" not in reply["html"].lower()
    assert "bits&amp;bytes™ Legal Agent" in reply["html"]
    assert "GOBITSNBYTES FOUNDATION" in reply["html"]
    import re
    assert not re.search(r"\b[0-9a-fA-F]{32}\b", reply["html"])
    assert not re.search(r"\b[0-9a-fA-F]{32}\b", reply["text"])


async def test_send_reply_rejects_self_or_daemon():
    settings = get_settings()
    assert legal_agent.send_reply(settings, "legal@gobitsnbytes.org", "test", "text", "html") is False
    assert legal_agent.send_reply(settings, "mailer-daemon@gobitsnbytes.org", "test", "text", "html") is False
    assert legal_agent.send_reply(settings, "bounces-123@sender-sib.com", "test", "text", "html") is False


async def test_clean_notion_title_and_content():
    raw_title = "💰 Sponsorships & Financial Limits 36449ed2fc33819b9d80fa3011f63ff7"
    cleaned_title = legal_agent._clean_notion_title(raw_title)
    assert "36449ed2fc33819b9d80fa3011f63ff7" not in cleaned_title
    assert "Sponsorships & Financial Limits" in cleaned_title

    raw_content = "# 💰 Sponsorships & Financial Limits 36449ed2fc33819b9d80fa3011f63ff7\nOwner: Bits Bytes\nOfficial bits&bytes legal document from notion-wiki\n## The central rule\nAll money must be routed through official systems."
    cleaned_content = legal_agent._clean_notion_content(raw_content)
    assert "36449ed2fc33819b9d80fa3011f63ff7" not in cleaned_content
    assert "Owner: Bits Bytes" not in cleaned_content
    assert "All money must be routed through official systems." in cleaned_content
