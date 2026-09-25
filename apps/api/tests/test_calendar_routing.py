import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import UUID

import httpx
from sqlalchemy import func, select

from app.db.models import (
    CalendarBooking,
    CalendarConnection,
    CalendarWebhookEvent,
    RoutingPool,
    RoutingPoolMember,
    RoutingDecision,
    User,
)
from app.services.calcom import CalComClient
from app.services.calendar_routing import reconcile_unknown_bookings
from conftest import request_as


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
        await cal.get_slots(
            7, "2026-10-01T00:00:00Z", "2026-10-02T00:00:00Z", "Asia/Kolkata"
        )
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
    connection_a = CalendarConnection(
        user_id=host_a.id, api_key="cal_a", status="active"
    )
    connection_b = CalendarConnection(
        user_id=host_b.id, api_key="cal_b", status="active"
    )
    pool = RoutingPool(name="Community", slug="community", created_by=owner.id)
    db_session.add_all([connection_a, connection_b, pool])
    await db_session.flush()
    member_a = RoutingPoolMember(
        pool_id=pool.id, calendar_connection_id=connection_a.id, event_type_id=101
    )
    member_b = RoutingPoolMember(
        pool_id=pool.id, calendar_connection_id=connection_b.id, event_type_id=202
    )
    db_session.add_all([member_a, member_b])
    await db_session.commit()
    return connection_a, pool, host_a, host_b


async def test_add_pool_member_accepts_current_calcom_google_meet_location(
    client, db_session
):
    connection, pool, _, _ = await _routing_setup(db_session)
    owner = await db_session.scalar(
        select(User).where(User.email == "owner@example.com")
    )
    with patch.object(
        CalComClient,
        "get_event_type",
        new=AsyncMock(
            return_value={
                "id": 303,
                "slug": "sponsor-call",
                "locations": [
                    {
                        "type": "integration",
                        "integration": "google-meet",
                        "credentialId": 123,
                    }
                ],
            }
        ),
    ):
        response = await request_as(
            client,
            owner.id,
            "POST",
            f"/api/calendar/routing-pools/{pool.id}/members",
            json={"calendar_connection_id": str(connection.id), "event_type_id": 303},
        )

    assert response.status_code == 201
    assert response.json()["event_type_id"] == 303


async def test_verify_connection_registers_supported_calcom_triggers(
    client, db_session
):
    connection, _, _, _ = await _routing_setup(db_session)
    owner = await db_session.scalar(
        select(User).where(User.email == "owner@example.com")
    )
    with (
        patch.object(
            CalComClient,
            "get_me",
            new=AsyncMock(return_value={"id": 1, "username": "host"}),
        ),
        patch.object(
            CalComClient, "create_webhook", new=AsyncMock(return_value={"id": 123})
        ) as create_mock,
    ):
        response = await request_as(
            client,
            owner.id,
            "POST",
            f"/api/calendar/connections/{connection.id}/verify",
        )

    assert response.status_code == 200
    assert response.json()["status"] == "active"
    kwargs = create_mock.await_args.kwargs
    assert kwargs["subscriber_url"].endswith(
        f"/api/calendar/webhooks/calcom/{connection.id}"
    )
    assert "BOOKING_LOCATION_UPDATED" not in kwargs["triggers"]
    assert {"BOOKING_CREATED", "BOOKING_RESCHEDULED", "BOOKING_CANCELLED"} <= set(
        kwargs["triggers"]
    )


async def test_shared_core_connection_creates_inactive_host_once(client, db_session):
    owner = User(display_name="Admin", is_super_admin=True)
    db_session.add(owner)
    await db_session.commit()
    owner_id = owner.id
    payload = {
        "shared_host_name": "bits&bytes",
        "shared_host_email": "gobitsnbytes@gmail.com",
        "api_key": "cal_core_secret",
    }

    first = await request_as(
        client, owner_id, "POST", "/api/calendar/connections/calcom", json=payload
    )
    repeated = await request_as(
        client, owner_id, "POST", "/api/calendar/connections/calcom", json=payload
    )

    assert first.status_code == 201
    assert repeated.status_code == 409
    host = await db_session.get(User, UUID(first.json()["user_id"]))
    assert host.display_name == payload["shared_host_name"]
    assert host.is_active is False
    assert host.email == payload["shared_host_email"]
    assert await db_session.scalar(select(func.count(User.id))) == 2

    with (
        patch.object(
            CalComClient,
            "get_me",
            new=AsyncMock(return_value={"id": 1, "email": "other@example.com"}),
        ),
        patch.object(
            CalComClient, "create_webhook", new=AsyncMock(return_value={"id": 123})
        ) as create_mock,
    ):
        mismatch = await request_as(
            client,
            owner_id,
            "POST",
            f"/api/calendar/connections/{first.json()['id']}/verify",
        )
    assert mismatch.status_code == 409
    create_mock.assert_not_awaited()

    with (
        patch.object(
            CalComClient,
            "get_me",
            new=AsyncMock(
                return_value={
                    "id": 1,
                    "username": "bitsandbytes",
                    "email": "gobitsnbytes@gmail.com",
                }
            ),
        ),
        patch.object(
            CalComClient, "create_webhook", new=AsyncMock(return_value={"id": 123})
        ) as create_mock,
    ):
        verified = await request_as(
            client,
            owner_id,
            "POST",
            f"/api/calendar/connections/{first.json()['id']}/verify",
        )
    assert verified.status_code == 200
    assert verified.json()["status"] == "active"
    create_mock.assert_awaited_once()


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

    with (
        patch.object(CalComClient, "get_slots", new=AsyncMock(return_value=slots)),
        patch.object(
            CalComClient, "create_booking", new=AsyncMock(side_effect=create)
        ) as create_mock,
    ):
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
    assert {first.json()["host_user_id"], second.json()["host_user_id"]} == {
        str(host_a.id),
        str(host_b.id),
    }
    assert create_mock.await_count == 2
    assert await db_session.scalar(select(func.count(CalendarBooking.id))) == 2


async def test_webhook_signature_and_duplicate_delivery(client, db_session):
    connection, pool, host, _ = await _routing_setup(db_session)
    connection.webhook_secret = "webhook-secret"
    member = await db_session.scalar(
        select(RoutingPoolMember).where(
            RoutingPoolMember.calendar_connection_id == connection.id
        )
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

    invalid = await client.post(
        path,
        content=body,
        headers={"content-type": "application/json", "x-cal-signature-256": "bad"},
    )
    first = await client.post(
        path,
        content=body,
        headers={"content-type": "application/json", "x-cal-signature-256": signature},
    )
    duplicate = await client.post(
        path,
        content=body,
        headers={"content-type": "application/json", "x-cal-signature-256": signature},
    )

    assert invalid.status_code == 401
    assert first.json() == {"status": "processed"}
    assert duplicate.json() == {"status": "duplicate"}
    await db_session.refresh(booking)
    assert booking.status == "cancelled"
    assert await db_session.scalar(select(func.count(CalendarWebhookEvent.id))) == 1


async def test_reconciliation_repairs_timeout_without_creating_again(db_session):
    connection, pool, host, _ = await _routing_setup(db_session)
    member = await db_session.scalar(
        select(RoutingPoolMember).where(
            RoutingPoolMember.calendar_connection_id == connection.id
        )
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
        "attendees": [
            {"name": "Guest", "email": "guest@example.com", "timeZone": "UTC"}
        ],
    }
    with (
        patch.object(
            CalComClient, "list_bookings", new=AsyncMock(return_value=[provider])
        ) as list_mock,
        patch.object(CalComClient, "create_booking", new=AsyncMock()) as create_mock,
    ):
        assert await reconcile_unknown_bookings(db_session) == 1

    await db_session.refresh(decision)
    assert decision.outcome == "completed"
    assert await db_session.scalar(
        select(CalendarBooking).where(
            CalendarBooking.provider_booking_uid == "reconciled-booking"
        )
    )
    assert list_mock.await_count == 1
    assert create_mock.await_count == 0
