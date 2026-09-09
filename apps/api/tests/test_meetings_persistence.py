"""Persistence tests for guest OTP verification, recording registration, and my-action-items."""

import hashlib
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.database import get_session
from app.db.models import ActionItem, BotMeeting, DiscordAccount, GuestVerification, User
from app.main import app
from conftest import request_as


@asynccontextmanager
async def _fresh_restart_session():
    """Session on a brand-new engine — simulates reading committed state after an app restart."""
    engine = create_async_engine(os.environ["DATABASE_URL"], poolclass=NullPool)
    try:
        maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with maker() as session:
            yield session
    finally:
        await engine.dispose()


@pytest.fixture(autouse=True)
def override_db(db_session: AsyncSession):
    async def _get_test_session():
        yield db_session

    app.dependency_overrides[get_session] = _get_test_session
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _make_meeting(meeting_id: str) -> BotMeeting:
    return BotMeeting(
        id=meeting_id,
        title=f"Meeting {meeting_id}",
        scheduled_time=1756000000000,
        location_type="discord_vc",
        status="scheduled",
        creator_id="tester_1",
        created_at=1756000000000,
        recording_status="none",
    )


@pytest.mark.asyncio
@patch("app.routers.meetings.send_smtp_email")
@patch("app.routers.meetings.random.randint", return_value=424242)
async def test_guest_otp_persists_across_restart(mock_randint, mock_send, client, db_session):
    resp = await client.post(
        "/api/meetings/public/guest/verification/send",
        json={"email": "guest@example.com"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "sent", "email": "guest@example.com"}

    # Simulated restart: a brand-new engine/session must see the persisted OTP row
    async with _fresh_restart_session() as fresh:
        res = await fresh.execute(
            select(GuestVerification).where(GuestVerification.email == "guest@example.com")
        )
        row = res.scalar_one()
        assert row.verified is False
        assert row.otp_hash == hashlib.sha256(b"424242").hexdigest()

    resp = await client.post(
        "/api/meetings/public/guest/verification/verify",
        json={"email": "guest@example.com", "code": "424242"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "verified"
    token = body["token"]

    # New session again: verified row holds the SHA-256 of the session token
    async with _fresh_restart_session() as fresh:
        res = await fresh.execute(
            select(GuestVerification).where(GuestVerification.email == "guest@example.com")
        )
        row = res.scalar_one()
        assert row.verified is True
        assert row.otp_hash == hashlib.sha256(token.encode()).hexdigest()


@pytest.mark.asyncio
async def test_expired_otp_rejected(client, db_session):
    now = datetime.now(timezone.utc)
    db_session.add(GuestVerification(
        email="late@example.com",
        otp_hash=hashlib.sha256(b"111111").hexdigest(),
        expires_at=now - timedelta(minutes=1),
        verified=False,
    ))
    await db_session.commit()

    resp = await client.post(
        "/api/meetings/public/guest/verification/verify",
        json={"email": "late@example.com", "code": "111111"},
    )
    assert resp.status_code == 400
    assert "expired" in resp.json()["detail"]

    res = await db_session.execute(
        select(GuestVerification).where(GuestVerification.email == "late@example.com")
    )
    assert res.scalar_one_or_none() is None


@pytest.mark.asyncio
@patch("app.routers.meetings.send_smtp_email")
@patch("app.routers.meetings.random.randint", return_value=555555)
async def test_wrong_otp_rejected(mock_randint, mock_send, client, db_session):
    resp = await client.post(
        "/api/meetings/public/guest/verification/send",
        json={"email": "wrong@example.com"},
    )
    assert resp.status_code == 200

    resp = await client.post(
        "/api/meetings/public/guest/verification/verify",
        json={"email": "wrong@example.com", "code": "999999"},
    )
    assert resp.status_code == 400
    assert "Invalid verification code" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_recording_register_flips_status_and_appears_in_detail(client, db_session, super_admin):
    db_session.add(_make_meeting("meet_rec_test_1"))
    await db_session.commit()

    resp = await request_as(
        client,
        super_admin.id,
        "POST",
        "/api/meetings/meet_rec_test_1/recording/register",
        json={
            "audio_url": "https://cdn.example.com/rec.ogg",
            "file_size_bytes": 1048576,
            "duration_seconds": 1800,
            "notes": "Full session audio",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["recording_status"] == "uploaded"
    assert data["recording_metadata"]["audio_url"] == "https://cdn.example.com/rec.ogg"
    assert data["recording_metadata"]["file_size_bytes"] == 1048576

    detail = await request_as(client, super_admin.id, "GET", "/api/meetings/meet_rec_test_1")
    assert detail.status_code == 200
    detail_data = detail.json()
    assert detail_data["recording_status"] == "uploaded"
    assert detail_data["recording_metadata"]["duration_seconds"] == 1800
    assert detail_data["recording_metadata"]["notes"] == "Full session audio"


@pytest.mark.asyncio
async def test_recording_register_internal_secret(client, db_session):
    db_session.add(_make_meeting("meet_rec_test_2"))
    await db_session.commit()

    resp = await client.request(
        "POST",
        "/api/meetings/meet_rec_test_2/recording/register",
        headers={"X-API-Secret": os.environ["API_INTERNAL_SECRET"]},
        json={"duration_seconds": 60},
    )
    assert resp.status_code == 200
    assert resp.json()["recording_status"] == "uploaded"

    unauth = await client.request(
        "POST",
        "/api/meetings/meet_rec_test_2/recording/register",
        headers={"X-API-Secret": "not-the-secret"},
        json={"duration_seconds": 60},
    )
    assert unauth.status_code == 401


@pytest.mark.asyncio
async def test_action_items_mine_returns_own_only(client, db_session):
    u1 = User(display_name="Alice", is_super_admin=True)
    u2 = User(display_name="Bob", is_super_admin=True)
    db_session.add_all([u1, u2])
    await db_session.flush()
    db_session.add_all([
        DiscordAccount(user_id=u1.id, discord_id="1001", username="alice"),
        DiscordAccount(user_id=u2.id, discord_id="2002", username="bob"),
    ])
    db_session.add_all([_make_meeting("meet_mine_1"), _make_meeting("meet_mine_2")])
    await db_session.flush()
    db_session.add_all([
        ActionItem(meeting_id="meet_mine_1", assignee="Alice", discord_id="1001", task="Alice task A", status="pending", created_at=1000),
        ActionItem(meeting_id="meet_mine_2", assignee="Alice", discord_id="1001", task="Alice task B", status="pending", created_at=2000),
        ActionItem(meeting_id="meet_mine_1", assignee="Bob", discord_id="2002", task="Bob task A", status="pending", created_at=3000),
        ActionItem(meeting_id="meet_mine_1", assignee="Alice", discord_id="1001", task="Alice done item", status="completed", created_at=4000),
    ])
    await db_session.commit()

    resp = await request_as(client, u1.id, "GET", "/api/meetings/action-items/mine")
    assert resp.status_code == 200
    items = resp.json()

    tasks = [i["task"] for i in items]
    assert tasks == ["Alice task B", "Alice task A"]
    assert items[0]["meeting_title"] == "Meeting meet_mine_2"
    assert items[0]["meeting_id"] == "meet_mine_2"
    assert all(i["status"] != "completed" for i in items)

    resp_bob = await request_as(client, u2.id, "GET", "/api/meetings/action-items/mine")
    assert resp_bob.status_code == 200
    assert [i["task"] for i in resp_bob.json()] == ["Bob task A"]

    # User with no linked Discord account sees no items
    u3 = User(display_name="No Discord", is_super_admin=True)
    db_session.add(u3)
    await db_session.commit()
    resp_none = await request_as(client, u3.id, "GET", "/api/meetings/action-items/mine")
    assert resp_none.status_code == 200
    assert resp_none.json() == []
