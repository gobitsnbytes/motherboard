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
        response = await client.post(
            "/api/contract-assistant/ask",
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

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/contract-assistant/ask",
            json={"question": "zzzzqqqq unrelated gibberish xyzzy"},
        )
        assert response.status_code == 200
        data = response.json()
    assert data["sources"] == []


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
