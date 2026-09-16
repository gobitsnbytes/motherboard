import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.database import get_session
from app.db.models import (
    CalendarBooking,
    CalendarConnection,
    CalendarWebhookEvent,
    RoutingPool,
    RoutingPoolMember,
    RoutingDecision,
    User,
)
from app.main import app
from app.services.calcom import CalComClient
from app.services.calendar_routing import reconcile_unknown_bookings


@pytest.fixture(autouse=True)
def override_db(db_session):
    async def _session():
        yield db_session

    app.dependency_overrides[get_session] = _session
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as value:
        yield value


@pytest.mark.asyncio
async def test_calcom_client_pins_headers_and_uses_event_type_location():
    requests = []

    async def handler(request: httpx.Request):
        requests.append(request)
        if request.url.path == "/v2/slots":
            return httpx.Response(200, json={"status": "success", "data": {}})
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "id": 1,
                    "uid": "book-1",
                    "start": "2026-10-01T10:00:00Z",
                    "end": "2026-10-01T10:30:00Z",
                },
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://api.cal.com"
    ) as http:
        cal = CalComClient("cal_secret", client=http)
        await cal.get_slots(7, "2026-10-01T00:00:00Z", "2026-10-02T00:00:00Z", "Asia/Kolkata")
        await cal.create_booking(
            event_type_id=7,
            start="2026-10-01T10:00:00Z",
            attendee_name="Guest",
            attendee_email="guest@example.com",
            attendee_time_zone="Asia/Kolkata",
        )

    assert requests[0].headers["authorization"] == "Bearer cal_secret"
    assert requests[0].headers["cal-api-version"] == CalComClient.SLOTS_VERSION
    assert requests[1].headers["cal-api-version"] == CalComClient.BOOKINGS_VERSION
    # The verified event type owns its Google Meet location. Sending a per-booking
    # override here would bypass that single source of truth.
    assert "location" not in json.loads(requests[1].content)


async def _routing_setup(db_session):
    owner = User(display_name="Owner", email="owner@example.com", is_super_admin=True)
    host_a = User(display_name="Host A", email="a@example.com")
    host_b = User(display_name="Host B", email="b@example.com")
    db_session.add_all([owner, host_a, host_b])
    await db_session.flush()
    connection_a = CalendarConnection(user_id=host_a.id, api_key="cal_a", status="active")
    connection_b = CalendarConnection(user_id=host_b.id, api_key="cal_b", status="active")
    pool = RoutingPool(name="Community", slug="community", created_by=owner.id)
    db_session.add_all([connection_a, connection_b, pool])
    await db_session.flush()
    member_a = RoutingPoolMember(pool_id=pool.id, calendar_connection_id=connection_a.id, event_type_id=101)
    member_b = RoutingPoolMember(pool_id=pool.id, calendar_connection_id=connection_b.id, event_type_id=202)
    db_session.add_all([member_a, member_b])
    await db_session.commit()
    return connection_a, pool, host_a, host_b


@pytest.mark.asyncio
async def test_public_booking_is_idempotent_and_round_robins(client, db_session):
    _, _, host_a, host_b = await _routing_setup(db_session)
    start = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=2)
    end = start + timedelta(minutes=30)
    slots = [{"start": start.isoformat(), "end": end.isoformat()}]
    created = 0

    async def create(**kwargs):
        nonlocal created
        created += 1
        return {
            "id": created,
            "uid": f"booking-{created}",
            "start": kwargs["start"],
            "end": end.isoformat(),
            "status": "accepted",
            "meetingUrl": f"https://meet.google.com/test-{created}",
        }

    with patch.object(CalComClient, "get_slots", new=AsyncMock(return_value=slots)), patch.object(
        CalComClient, "create_booking", new=AsyncMock(side_effect=create)
    ) as create_mock:
        payload = {
            "start": start.isoformat(),
            "attendee_name": "Guest",
            "attendee_email": "guest@example.com",
            "attendee_timezone": "Asia/Kolkata",
        }
        first = await client.post(
            "/api/calendar/public/community/book",
            headers={"Idempotency-Key": "booking-request-one"},
            json=payload,
        )
        duplicate = await client.post(
            "/api/calendar/public/community/book",
            headers={"Idempotency-Key": "booking-request-one"},
            json=payload,
        )
        mismatched = await client.post(
            "/api/calendar/public/community/book",
            headers={"Idempotency-Key": "booking-request-one"},
            json={**payload, "attendee_email": "different@example.com"},
        )
        second = await client.post(
            "/api/calendar/public/community/book",
            headers={"Idempotency-Key": "booking-request-two"},
            json={**payload, "attendee_email": "other@example.com"},
        )

    assert first.status_code == 201, first.text
    assert duplicate.status_code == 201, duplicate.text
    assert mismatched.status_code == 409
    assert second.status_code == 201, second.text
    assert first.json()["uid"] == duplicate.json()["uid"]
    assert {first.json()["host_user_id"], second.json()["host_user_id"]} == {str(host_a.id), str(host_b.id)}
    assert create_mock.await_count == 2
    assert await db_session.scalar(select(func.count(CalendarBooking.id))) == 2


@pytest.mark.asyncio
async def test_webhook_signature_and_duplicate_delivery(client, db_session):
    connection, pool, host, _ = await _routing_setup(db_session)
    connection.webhook_secret = "webhook-secret"
    member = await db_session.scalar(
        select(RoutingPoolMember).where(RoutingPoolMember.calendar_connection_id == connection.id)
    )
    start = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=1)
    booking = CalendarBooking(
        provider_booking_uid="webhook-booking",
        routing_pool_id=pool.id,
        routing_pool_member_id=member.id,
        event_type_id=member.event_type_id,
        host_user_id=host.id,
        attendee_name="Guest",
        attendee_email="guest@example.com",
        attendee_timezone="UTC",
        start_at=start,
        end_at=start + timedelta(minutes=30),
        status="accepted",
    )
    db_session.add(booking)
    await db_session.commit()
    body = json.dumps(
        {
            "triggerEvent": "BOOKING_CANCELLED",
            "createdAt": "2026-09-16T10:00:00Z",
            "payload": {"uid": "webhook-booking"},
        },
        separators=(",", ":"),
    ).encode()
    signature = hmac.new(b"webhook-secret", body, hashlib.sha256).hexdigest()
    path = f"/api/calendar/webhooks/calcom/{connection.id}"

    invalid = await client.post(path, content=body, headers={"content-type": "application/json", "x-cal-signature-256": "bad"})
    first = await client.post(path, content=body, headers={"content-type": "application/json", "x-cal-signature-256": signature})
    duplicate = await client.post(path, content=body, headers={"content-type": "application/json", "x-cal-signature-256": signature})

    assert invalid.status_code == 401
    assert first.json() == {"status": "processed"}
    assert duplicate.json() == {"status": "duplicate"}
    await db_session.refresh(booking)
    assert booking.status == "cancelled"
    assert await db_session.scalar(select(func.count(CalendarWebhookEvent.id))) == 1


@pytest.mark.asyncio
async def test_reconciliation_repairs_timeout_without_creating_again(db_session):
    connection, pool, host, _ = await _routing_setup(db_session)
    member = await db_session.scalar(
        select(RoutingPoolMember).where(RoutingPoolMember.calendar_connection_id == connection.id)
    )
    decision = RoutingDecision(
        idempotency_key="create:pool:timeout",
        routing_pool_id=pool.id,
        requested_start_at=datetime.now(timezone.utc),
        selected_member_id=member.id,
        outcome="unknown",
    )
    db_session.add(decision)
    await db_session.commit()
    provider = {
        "id": 44,
        "uid": "reconciled-booking",
        "start": "2026-10-01T10:00:00Z",
        "end": "2026-10-01T10:30:00Z",
        "status": "accepted",
        "meetingUrl": "https://meet.google.com/reconciled",
        "metadata": {"motherboardRoutingDecisionId": str(decision.id)},
        "attendees": [{"name": "Guest", "email": "guest@example.com", "timeZone": "UTC"}],
    }
    with patch.object(CalComClient, "list_bookings", new=AsyncMock(return_value=[provider])) as list_mock, patch.object(
        CalComClient, "create_booking", new=AsyncMock()
    ) as create_mock:
        assert await reconcile_unknown_bookings(db_session) == 1

    await db_session.refresh(decision)
    assert decision.outcome == "completed"
    assert await db_session.scalar(
        select(CalendarBooking).where(CalendarBooking.provider_booking_uid == "reconciled-booking")
    )
    assert list_mock.await_count == 1
    assert create_mock.await_count == 0
