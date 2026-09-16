from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.db.models import (
    CalendarBooking,
    CalendarConnection,
    CalendarWebhookEvent,
    RoutingDecision,
    RoutingPool,
    RoutingPoolMember,
    User,
)
from app.dependencies import CurrentUserDep, DbSession
from app.iam.policy import require_permission
from app.schemas.calendar import (
    BookingMutation,
    BookingOut,
    BookingReschedule,
    AdminBookingOut,
    ConnectionCreate,
    ConnectionOut,
    PoolMemberCreate,
    PoolMemberOut,
    PublicBookingCreate,
    RoutingPoolCreate,
    RoutingPoolOut,
    RoutingPoolPatch,
    SlotOut,
    WebhookAck,
)
from app.services.calendar_routing import _dt, aggregate_slots, create_routed_booking
from app.services.calcom import CalComClient, CalComError


router = APIRouter(prefix="/api/calendar", tags=["calendar"])
WEBHOOK_TRIGGERS = [
    "BOOKING_CREATED",
    "BOOKING_RESCHEDULED",
    "BOOKING_CANCELLED",
    "BOOKING_REJECTED",
    "BOOKING_NO_SHOW_UPDATED",
    "MEETING_STARTED",
    "MEETING_ENDED",
]


def _booking_token(uid: str, email: str) -> str:
    message = f"{uid}:{email.lower()}".encode()
    return hmac.new(get_settings().session_secret.encode(), message, hashlib.sha256).hexdigest()


def _require_booking_token(booking: CalendarBooking, token: str | None) -> None:
    if not token or not hmac.compare_digest(token, _booking_token(booking.provider_booking_uid, booking.attendee_email)):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid booking management token")


def _booking_out(booking: CalendarBooking) -> BookingOut:
    return BookingOut(
        uid=booking.provider_booking_uid,
        status=booking.status,
        start=booking.start_at,
        end=booking.end_at,
        meeting_url=booking.meeting_url,
        host_user_id=booking.host_user_id,
        management_token=_booking_token(booking.provider_booking_uid, booking.attendee_email),
    )


async def _pool_or_404(db: DbSession, slug: str) -> RoutingPool:
    pool = await db.scalar(select(RoutingPool).where(RoutingPool.slug == slug, RoutingPool.active.is_(True)))
    if not pool:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Routing pool not found")
    return pool


@router.get("/connections", response_model=list[ConnectionOut])
async def list_connections(db: DbSession, current_user: CurrentUserDep):
    await require_permission(db, current_user, "meetings.read")
    return list((await db.scalars(select(CalendarConnection).order_by(CalendarConnection.created_at))).all())


@router.post("/connections/calcom", response_model=ConnectionOut, status_code=status.HTTP_201_CREATED)
async def create_connection(body: ConnectionCreate, db: DbSession, current_user: CurrentUserDep):
    await require_permission(db, current_user, "meetings.write")
    if not await db.get(User, body.user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    connection = CalendarConnection(user_id=body.user_id, api_key=body.api_key)
    db.add(connection)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "This user already has a Cal.com connection") from exc
    await db.refresh(connection)
    return connection


@router.post("/connections/{connection_id}/verify", response_model=ConnectionOut)
async def verify_connection(connection_id: UUID, db: DbSession, current_user: CurrentUserDep):
    await require_permission(db, current_user, "meetings.write")
    connection = await db.get(CalendarConnection, connection_id)
    if not connection or connection.status == "revoked":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Connection not found")
    client = CalComClient(connection.api_key)
    try:
        profile = await client.get_me()
        connection.cal_user_id = str(profile.get("id")) if profile.get("id") is not None else None
        connection.cal_username = profile.get("username")
        connection.webhook_secret = connection.webhook_secret or secrets.token_urlsafe(32)
        if not connection.provider_webhook_id:
            settings = get_settings()
            # Prefer an explicit public API origin. Otherwise route through the
            # authenticated web app's deliberately public, signature-verified proxy.
            webhook_base = settings.calendar_webhook_base_url or settings.nextauth_url
            callback = f"{webhook_base.rstrip('/')}/api/calendar/webhooks/calcom/{connection.id}"
            webhook = await client.create_webhook(
                subscriber_url=callback, secret=connection.webhook_secret, triggers=WEBHOOK_TRIGGERS
            )
            connection.provider_webhook_id = str(webhook.get("id")) if webhook.get("id") is not None else None
        connection.status = "active"
        connection.last_error_code = None
        connection.last_verified_at = datetime.now(timezone.utc)
    except CalComError as exc:
        connection.status = "invalid"
        connection.last_error_code = exc.code
        await db.commit()
        raise HTTPException(exc.status_code, "Cal.com connection verification failed") from exc
    await db.commit()
    await db.refresh(connection)
    return connection


@router.delete("/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_connection(connection_id: UUID, db: DbSession, current_user: CurrentUserDep):
    await require_permission(db, current_user, "meetings.write")
    connection = await db.get(CalendarConnection, connection_id)
    if not connection:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Connection not found")
    if connection.provider_webhook_id:
        try:
            await CalComClient(connection.api_key).delete_webhook(connection.provider_webhook_id)
        except CalComError:
            pass
    connection.status = "revoked"
    connection.provider_webhook_id = None
    await db.commit()


@router.get("/routing-pools", response_model=list[RoutingPoolOut])
async def list_pools(db: DbSession, current_user: CurrentUserDep):
    await require_permission(db, current_user, "meetings.read")
    return list((await db.scalars(select(RoutingPool).order_by(RoutingPool.name))).all())


@router.post("/routing-pools", response_model=RoutingPoolOut, status_code=status.HTTP_201_CREATED)
async def create_pool(body: RoutingPoolCreate, db: DbSession, current_user: CurrentUserDep):
    await require_permission(db, current_user, "meetings.write")
    pool = RoutingPool(**body.model_dump(), created_by=current_user.user_id)
    db.add(pool)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Routing pool slug already exists") from exc
    await db.refresh(pool)
    return pool


@router.patch("/routing-pools/{pool_id}", response_model=RoutingPoolOut)
async def patch_pool(pool_id: UUID, body: RoutingPoolPatch, db: DbSession, current_user: CurrentUserDep):
    await require_permission(db, current_user, "meetings.write")
    pool = await db.get(RoutingPool, pool_id)
    if not pool:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Routing pool not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(pool, key, value)
    await db.commit()
    await db.refresh(pool)
    return pool


@router.post("/routing-pools/{pool_id}/members", response_model=PoolMemberOut, status_code=status.HTTP_201_CREATED)
async def add_pool_member(pool_id: UUID, body: PoolMemberCreate, db: DbSession, current_user: CurrentUserDep):
    await require_permission(db, current_user, "meetings.write")
    pool = await db.get(RoutingPool, pool_id)
    connection = await db.get(CalendarConnection, body.calendar_connection_id)
    if not pool or not connection or connection.status != "active":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Active pool and connection are required")
    try:
        event_type = await CalComClient(connection.api_key).get_event_type(body.event_type_id)
    except CalComError as exc:
        raise HTTPException(exc.status_code, "Cal.com event type verification failed") from exc
    locations = event_type.get("locations") or []
    location_types = {str(item.get("type", "")).lower() for item in locations if isinstance(item, dict)}
    if not ({"google_meet", "integrations:google:meet"} & location_types):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Event type must use Google Meet")
    member = RoutingPoolMember(
        pool_id=pool_id,
        event_type_slug=event_type.get("slug"),
        **body.model_dump(),
    )
    db.add(member)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Event type is already in this pool") from exc
    await db.refresh(member)
    return member


@router.get("/routing-pools/{pool_id}/members", response_model=list[PoolMemberOut])
async def list_pool_members(pool_id: UUID, db: DbSession, current_user: CurrentUserDep):
    await require_permission(db, current_user, "meetings.read")
    if not await db.get(RoutingPool, pool_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Routing pool not found")
    return list(
        (await db.scalars(
            select(RoutingPoolMember)
            .where(RoutingPoolMember.pool_id == pool_id, RoutingPoolMember.active.is_(True))
            .order_by(RoutingPoolMember.priority, RoutingPoolMember.created_at)
        )).all()
    )


@router.delete("/routing-pools/{pool_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_pool_member(pool_id: UUID, member_id: UUID, db: DbSession, current_user: CurrentUserDep):
    await require_permission(db, current_user, "meetings.write")
    member = await db.scalar(
        select(RoutingPoolMember).where(RoutingPoolMember.id == member_id, RoutingPoolMember.pool_id == pool_id)
    )
    if not member:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pool member not found")
    member.active = False
    await db.commit()


@router.get("/bookings", response_model=list[AdminBookingOut])
async def list_bookings(db: DbSession, current_user: CurrentUserDep):
    await require_permission(db, current_user, "meetings.read")
    return list((await db.scalars(select(CalendarBooking).order_by(CalendarBooking.start_at.desc()))).all())


@router.get("/public/{pool_slug}/slots", response_model=list[SlotOut])
async def public_slots(
    pool_slug: str,
    db: DbSession,
    start: datetime = Query(),
    end: datetime = Query(),
    time_zone: str = Query(min_length=1, max_length=100),
):
    if start.tzinfo is None or end.tzinfo is None or end <= start or end - start > timedelta(days=31):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid slot range")
    pool = await _pool_or_404(db, pool_slug)
    return await aggregate_slots(db, pool, start=start, end=end, time_zone=time_zone)


@router.post("/public/{pool_slug}/book", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
async def public_book(
    pool_slug: str,
    body: PublicBookingCreate,
    db: DbSession,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=255),
):
    pool = await _pool_or_404(db, pool_slug)
    return _booking_out(await create_routed_booking(db, pool, body, idempotency_key))


async def _mutation_decision(db: DbSession, booking: CalendarBooking, key: str, action: str) -> RoutingDecision:
    namespaced = f"{action}:{booking.provider_booking_uid}:{key}"
    existing = await db.scalar(select(RoutingDecision).where(RoutingDecision.idempotency_key == namespaced))
    if existing:
        return existing
    decision = RoutingDecision(
        idempotency_key=namespaced,
        routing_pool_id=booking.routing_pool_id,
        requested_start_at=booking.start_at,
        selected_member_id=booking.routing_pool_member_id,
        outcome="pending",
    )
    db.add(decision)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return await db.scalar(select(RoutingDecision).where(RoutingDecision.idempotency_key == namespaced))
    return decision


@router.post("/public/bookings/{uid}/reschedule", response_model=BookingOut)
async def public_reschedule(
    uid: str,
    body: BookingReschedule,
    db: DbSession,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=255),
    booking_token: str | None = Header(default=None, alias="X-Booking-Token"),
):
    booking = await db.scalar(select(CalendarBooking).where(CalendarBooking.provider_booking_uid == uid))
    if not booking:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    _require_booking_token(booking, booking_token)
    decision = await _mutation_decision(db, booking, idempotency_key, "reschedule")
    if decision.outcome == "completed" and decision.provider_booking_uid:
        completed = await db.scalar(select(CalendarBooking).where(CalendarBooking.provider_booking_uid == decision.provider_booking_uid))
        return _booking_out(completed)
    if decision.outcome in {"unknown", "failed"}:
        raise HTTPException(status.HTTP_409_CONFLICT, decision.reason or "Reschedule already failed")
    connection = await db.scalar(
        select(CalendarConnection)
        .join(RoutingPoolMember, RoutingPoolMember.calendar_connection_id == CalendarConnection.id)
        .where(RoutingPoolMember.id == booking.routing_pool_member_id)
    )
    try:
        provider = await CalComClient(connection.api_key).reschedule_booking(
            uid, start=body.start.isoformat(), reason=body.reason
        )
    except CalComError as exc:
        decision.outcome = "unknown" if exc.retryable else "failed"
        decision.reason = exc.code
        await db.commit()
        raise HTTPException(exc.status_code, "Cal.com could not reschedule the booking") from exc
    new_uid = str(provider.get("uid") or uid)
    booking.rescheduled_from_uid = uid if new_uid != uid else booking.rescheduled_from_uid
    booking.provider_booking_uid = new_uid
    booking.start_at = _dt(provider.get("start") or body.start)
    booking.end_at = _dt(provider.get("end") or booking.end_at)
    booking.status = str(provider.get("status") or "accepted")
    booking.provider_payload = provider
    decision.outcome = "completed"
    decision.provider_booking_uid = new_uid
    await db.commit()
    return _booking_out(booking)


@router.post("/public/bookings/{uid}/cancel", response_model=BookingOut)
async def public_cancel(
    uid: str,
    body: BookingMutation,
    db: DbSession,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=255),
    booking_token: str | None = Header(default=None, alias="X-Booking-Token"),
):
    booking = await db.scalar(select(CalendarBooking).where(CalendarBooking.provider_booking_uid == uid))
    if not booking:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    _require_booking_token(booking, booking_token)
    decision = await _mutation_decision(db, booking, idempotency_key, "cancel")
    if decision.outcome == "completed":
        return _booking_out(booking)
    if decision.outcome in {"unknown", "failed"}:
        raise HTTPException(status.HTTP_409_CONFLICT, decision.reason or "Cancellation already failed")
    connection = await db.scalar(
        select(CalendarConnection)
        .join(RoutingPoolMember, RoutingPoolMember.calendar_connection_id == CalendarConnection.id)
        .where(RoutingPoolMember.id == booking.routing_pool_member_id)
    )
    try:
        await CalComClient(connection.api_key).cancel_booking(uid, reason=body.reason)
    except CalComError as exc:
        decision.outcome = "unknown" if exc.retryable else "failed"
        decision.reason = exc.code
        await db.commit()
        raise HTTPException(exc.status_code, "Cal.com could not cancel the booking") from exc
    booking.status = "cancelled"
    decision.outcome = "completed"
    decision.provider_booking_uid = uid
    await db.commit()
    return _booking_out(booking)


@router.post("/webhooks/calcom/{connection_id}", response_model=WebhookAck)
async def calcom_webhook(
    connection_id: UUID,
    request: Request,
    db: DbSession,
    signature: str | None = Header(default=None, alias="x-cal-signature-256"),
):
    connection = await db.get(CalendarConnection, connection_id)
    if not connection or not connection.webhook_secret:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook connection not found")
    raw = await request.body()
    expected = hmac.new(connection.webhook_secret.encode(), raw, hashlib.sha256).hexdigest()
    supplied = signature.removeprefix("sha256=") if signature else ""
    if not hmac.compare_digest(expected, supplied):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid webhook signature")
    try:
        body = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid webhook payload") from exc
    trigger = str(body.get("triggerEvent") or body.get("trigger") or "")
    payload = body.get("payload") if isinstance(body.get("payload"), dict) else body
    uid = payload.get("uid") or payload.get("bookingUid")
    created = body.get("createdAt") or payload.get("createdAt") or ""
    event_key = hashlib.sha256(f"{trigger}:{uid}:{created}".encode()).hexdigest()
    event = CalendarWebhookEvent(
        connection_id=connection.id,
        event_key=event_key,
        trigger=trigger[:80],
        booking_uid=str(uid) if uid else None,
        payload=body,
    )
    db.add(event)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return WebhookAck(status="duplicate")
    booking = None
    if uid:
        booking = await db.scalar(select(CalendarBooking).where(CalendarBooking.provider_booking_uid == str(uid)))
    if booking:
        status_by_trigger = {
            "BOOKING_CANCELLED": "cancelled",
            "BOOKING_REJECTED": "rejected",
            "BOOKING_CREATED": str(payload.get("status") or "accepted"),
            "BOOKING_RESCHEDULED": str(payload.get("status") or "accepted"),
        }
        if trigger in status_by_trigger:
            booking.status = status_by_trigger[trigger]
        if payload.get("startTime") or payload.get("start"):
            booking.start_at = _dt(payload.get("startTime") or payload.get("start"))
        if payload.get("endTime") or payload.get("end"):
            booking.end_at = _dt(payload.get("endTime") or payload.get("end"))
        booking.meeting_url = payload.get("meetingUrl") or booking.meeting_url
        booking.provider_payload = payload
    event.status = "processed"
    event.processed_at = datetime.now(timezone.utc)
    event.attempt_count = 1
    await db.commit()
    return WebhookAck(status="processed")
