from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    CalendarBooking,
    CalendarConnection,
    RoutingDecision,
    RoutingPool,
    RoutingPoolMember,
)
from app.schemas.calendar import PublicBookingCreate
from app.services.calcom import CalComClient, CalComError


def _dt(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _assignment_order(value: datetime | None) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def extract_slots(payload: Any) -> list[tuple[datetime, datetime]]:
    """Accept Cal.com's range response while ignoring unrelated response fields."""
    found: list[tuple[datetime, datetime]] = []
    if isinstance(payload, dict):
        if isinstance(payload.get("start"), str) and isinstance(payload.get("end"), str):
            found.append((_dt(payload["start"]), _dt(payload["end"])))
        else:
            for value in payload.values():
                found.extend(extract_slots(value))
    elif isinstance(payload, list):
        for value in payload:
            found.extend(extract_slots(value))
    return found


async def _active_members(db: AsyncSession, pool_id, *, lock: bool = False):
    stmt = (
        select(RoutingPoolMember, CalendarConnection)
        .join(CalendarConnection, CalendarConnection.id == RoutingPoolMember.calendar_connection_id)
        .where(
            RoutingPoolMember.pool_id == pool_id,
            RoutingPoolMember.active.is_(True),
            CalendarConnection.status == "active",
        )
    )
    if lock and db.bind and db.bind.dialect.name != "sqlite":
        stmt = stmt.with_for_update(of=RoutingPoolMember)
    return (await db.execute(stmt)).all()


async def aggregate_slots(
    db: AsyncSession,
    pool: RoutingPool,
    *,
    start: datetime,
    end: datetime,
    time_zone: str,
) -> list[dict[str, datetime]]:
    members = await _active_members(db, pool.id)

    async def fetch(member: RoutingPoolMember, connection: CalendarConnection):
        try:
            data = await CalComClient(connection.api_key).get_slots(
                member.event_type_id, _iso(start), _iso(end), time_zone
            )
            return extract_slots(data)
        except CalComError as exc:
            connection.last_error_code = exc.code
            if not exc.retryable:
                connection.status = "invalid"
            return []

    results = await asyncio.gather(*(fetch(member, connection) for member, connection in members))
    unique = {(slot_start, slot_end) for slots in results for slot_start, slot_end in slots}
    await db.commit()
    return [{"start": slot_start, "end": slot_end} for slot_start, slot_end in sorted(unique)]


async def _eligible_for_start(
    rows: list[tuple[RoutingPoolMember, CalendarConnection]], start: datetime, time_zone: str
) -> list[tuple[RoutingPoolMember, CalendarConnection, datetime]]:
    range_start = start - timedelta(minutes=1)
    range_end = start + timedelta(days=1)

    async def check(member: RoutingPoolMember, connection: CalendarConnection):
        try:
            payload = await CalComClient(connection.api_key).get_slots(
                member.event_type_id, _iso(range_start), _iso(range_end), time_zone
            )
            for slot_start, slot_end in extract_slots(payload):
                if slot_start.astimezone(timezone.utc) == start.astimezone(timezone.utc):
                    return member, connection, slot_end
        except CalComError:
            return None
        return None

    checked = await asyncio.gather(*(check(member, connection) for member, connection in rows))
    return [candidate for candidate in checked if candidate is not None]


async def _choose_member(
    db: AsyncSession,
    pool: RoutingPool,
    candidates: list[tuple[RoutingPoolMember, CalendarConnection, datetime]],
) -> tuple[RoutingPoolMember, CalendarConnection, datetime]:
    if pool.algorithm == "priority":
        best_priority = min(member.priority for member, _, _ in candidates)
        candidates = [row for row in candidates if row[0].priority == best_priority]
    if pool.algorithm == "weighted_round_robin":
        since = datetime.now(timezone.utc) - timedelta(days=30)
        counts = dict(
            (await db.execute(
                select(CalendarBooking.routing_pool_member_id, func.count(CalendarBooking.id))
                .where(
                    CalendarBooking.routing_pool_id == pool.id,
                    CalendarBooking.created_at >= since,
                    CalendarBooking.status != "cancelled",
                )
                .group_by(CalendarBooking.routing_pool_member_id)
            )).all()
        )
        return min(
            candidates,
            key=lambda row: (
                counts.get(row[0].id, 0) / row[0].weight,
                _assignment_order(row[0].last_assigned_at),
            ),
        )
    return min(
        candidates,
        key=lambda row: _assignment_order(row[0].last_assigned_at),
    )


async def create_routed_booking(
    db: AsyncSession,
    pool: RoutingPool,
    request: PublicBookingCreate,
    idempotency_key: str,
) -> CalendarBooking:
    stored_key = f"create:{pool.id}:{idempotency_key}"
    request_hash = hashlib.sha256(
        json.dumps(request.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    attendee_hash = hashlib.sha256(str(request.attendee_email).lower().encode()).hexdigest()
    existing = await db.scalar(select(RoutingDecision).where(RoutingDecision.idempotency_key == stored_key))
    if existing:
        if (existing.response_payload or {}).get("request_hash") not in {None, request_hash}:
            raise HTTPException(status.HTTP_409_CONFLICT, "Idempotency key was already used with different booking details")
        if existing.outcome == "completed" and existing.provider_booking_uid:
            booking = await db.scalar(
                select(CalendarBooking).where(CalendarBooking.provider_booking_uid == existing.provider_booking_uid)
            )
            if booking:
                return booking
        if existing.outcome in {"pending", "unknown"}:
            raise HTTPException(status.HTTP_409_CONFLICT, "Booking is already being processed; do not retry with a new key")
        raise HTTPException(status.HTTP_409_CONFLICT, existing.reason or "Booking request already failed")

    recent_since = datetime.now(timezone.utc) - timedelta(minutes=10)
    recent = list(
        (await db.scalars(
            select(RoutingDecision)
            .where(RoutingDecision.routing_pool_id == pool.id, RoutingDecision.created_at >= recent_since)
            .order_by(RoutingDecision.created_at.desc())
            .limit(100)
        )).all()
    )
    if len(recent) >= 100 or sum(
        1 for item in recent if (item.response_payload or {}).get("attendee_hash") == attendee_hash
    ) >= 5:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many booking attempts; try again later")

    decision = RoutingDecision(
        idempotency_key=stored_key,
        routing_pool_id=pool.id,
        requested_start_at=request.start,
        outcome="pending",
        response_payload={"request_hash": request_hash, "attendee_hash": attendee_hash},
    )
    db.add(decision)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return await create_routed_booking(db, pool, request, idempotency_key)

    pool = await db.scalar(select(RoutingPool).where(RoutingPool.id == pool.id).with_for_update())
    rows = await _active_members(db, pool.id, lock=True)
    candidates = await _eligible_for_start(rows, request.start, request.attendee_timezone)
    day_start = request.start.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    eligible = []
    for candidate in candidates:
        member = candidate[0]
        if member.daily_booking_limit is None:
            eligible.append(candidate)
            continue
        count = await db.scalar(
            select(func.count(CalendarBooking.id)).where(
                CalendarBooking.routing_pool_member_id == member.id,
                CalendarBooking.start_at >= day_start,
                CalendarBooking.start_at < day_end,
                CalendarBooking.status != "cancelled",
            )
        )
        if (count or 0) < member.daily_booking_limit:
            eligible.append(candidate)
    candidates = eligible
    decision = await db.scalar(select(RoutingDecision).where(RoutingDecision.id == decision.id))
    decision.candidate_snapshot = [
        {"member_id": str(member.id), "event_type_id": member.event_type_id}
        for member, _, _ in candidates
    ]
    if not candidates:
        decision.outcome = "failed"
        decision.reason = "slot_unavailable"
        await db.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, "That slot is no longer available")

    member, connection, slot_end = await _choose_member(db, pool, candidates)
    decision.selected_member_id = member.id
    await db.flush()

    try:
        provider = await CalComClient(connection.api_key).create_booking(
            event_type_id=member.event_type_id,
            start=_iso(request.start),
            attendee_name=request.attendee_name,
            attendee_email=str(request.attendee_email),
            attendee_time_zone=request.attendee_timezone,
            guests=[str(email) for email in request.guest_emails] or None,
            metadata={"motherboardRoutingDecisionId": str(decision.id)},
        )
    except CalComError as exc:
        decision = await db.scalar(select(RoutingDecision).where(RoutingDecision.id == decision.id))
        decision.outcome = "unknown" if exc.retryable else "failed"
        decision.reason = exc.code
        await db.commit()
        raise HTTPException(exc.status_code, "Cal.com could not complete the booking") from exc

    uid = str(provider.get("uid") or "")
    if not uid:
        decision.outcome = "unknown"
        decision.reason = "calcom_missing_booking_uid"
        await db.commit()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Cal.com returned an incomplete booking")
    start_at = _dt(provider.get("start") or request.start)
    end_at = _dt(provider.get("end") or slot_end)
    meeting_url = provider.get("meetingUrl") or provider.get("videoCallUrl")
    if not meeting_url and isinstance(provider.get("location"), str):
        meeting_url = provider["location"]
    booking = CalendarBooking(
        provider_booking_uid=uid,
        provider_booking_id=str(provider["id"]) if provider.get("id") is not None else None,
        routing_pool_id=pool.id,
        routing_pool_member_id=member.id,
        event_type_id=member.event_type_id,
        host_user_id=connection.user_id,
        attendee_name=request.attendee_name,
        attendee_email=str(request.attendee_email),
        attendee_timezone=request.attendee_timezone,
        guest_emails=[str(email) for email in request.guest_emails] or None,
        start_at=start_at,
        end_at=end_at,
        status=str(provider.get("status") or "accepted"),
        meeting_url=meeting_url,
        provider_payload=provider,
    )
    db.add(booking)
    member.last_assigned_at = datetime.now(timezone.utc)
    decision.outcome = "completed"
    decision.provider_booking_uid = uid
    decision.response_payload = {"uid": uid, "request_hash": request_hash, "attendee_hash": attendee_hash}
    await db.commit()
    await db.refresh(booking)
    return booking


async def reconcile_unknown_bookings(db: AsyncSession) -> int:
    """Repair local rows after a provider timeout. This function only reads Cal.com."""
    decisions = list(
        (await db.scalars(
            select(RoutingDecision)
            .where(RoutingDecision.outcome == "unknown", RoutingDecision.selected_member_id.is_not(None))
            .order_by(RoutingDecision.created_at)
            .limit(100)
        )).all()
    )
    repaired = 0
    for decision in decisions:
        member = await db.get(RoutingPoolMember, decision.selected_member_id)
        connection = await db.get(CalendarConnection, member.calendar_connection_id) if member else None
        if not member or not connection or connection.status != "active":
            continue
        created_at = decision.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        try:
            provider_rows = await CalComClient(connection.api_key).list_bookings(
                event_type_id=member.event_type_id,
                after_created_at=_iso(created_at - timedelta(minutes=5)),
            )
        except CalComError:
            continue
        provider = next(
            (
                row for row in provider_rows
                if str((row.get("metadata") or {}).get("motherboardRoutingDecisionId")) == str(decision.id)
            ),
            None,
        )
        if not provider or not provider.get("uid"):
            continue
        uid = str(provider["uid"])
        existing = await db.scalar(select(CalendarBooking).where(CalendarBooking.provider_booking_uid == uid))
        if not existing:
            attendee = ((provider.get("attendees") or [{}])[0])
            if not attendee.get("email") or not provider.get("start") or not provider.get("end"):
                continue
            db.add(CalendarBooking(
                provider_booking_uid=uid,
                provider_booking_id=str(provider["id"]) if provider.get("id") is not None else None,
                routing_pool_id=decision.routing_pool_id,
                routing_pool_member_id=member.id,
                event_type_id=member.event_type_id,
                host_user_id=connection.user_id,
                attendee_name=str(attendee.get("name") or "Attendee"),
                attendee_email=str(attendee["email"]),
                attendee_timezone=str(attendee.get("timeZone") or "UTC"),
                guest_emails=provider.get("guests") or None,
                start_at=_dt(provider["start"]),
                end_at=_dt(provider["end"]),
                status=str(provider.get("status") or "accepted"),
                meeting_url=provider.get("meetingUrl") or provider.get("location"),
                provider_payload=provider,
            ))
        decision.outcome = "completed"
        decision.reason = "reconciled_after_timeout"
        decision.provider_booking_uid = uid
        decision.response_payload = {**(decision.response_payload or {}), "uid": uid}
        member.last_assigned_at = datetime.now(timezone.utc)
        repaired += 1
    await db.commit()
    return repaired
