"""
Transactional workflow operations for Dyslexic.

Every function here takes an ``AsyncSession`` and **does not commit** — the
caller owns the transaction, matching the convention `write_audit_entry` already
established. Routers commit and then publish to the event bus; publishing before
the commit would announce state that might roll back.

The module's two hard guarantees live in this file:

* a contact receives at most one ``initial`` outreach, and
* a contact has at most one ``pending`` follow-up.

The first is also enforced by a partial unique index, so a race between two
requests fails at the database rather than producing a duplicate. The check here
exists to turn that into a readable message instead of a 500.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    DyslexicCompany,
    DyslexicContact,
    DyslexicEvent,
    DyslexicFollowUp,
    DyslexicOutreach,
    User,
)
from app.iam.audit import write_audit_entry

from .constants import (
    CLAIM_MINUTES,
    FOLLOW_UP_INTERVAL_DAYS,
    OUTCOME_CONTACT_STATUS_MAP,
    OUTCOME_STAGE_MAP,
    OUTREACH_OUTCOMES,
    advance_stage,
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class DyslexicError(Exception):
    """Base for workflow errors. `detail` is returned to the client as-is."""

    status_code = 400

    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(message)
        self.detail: dict[str, Any] = {"message": message, **context}


class NotFound(DyslexicError):
    status_code = 404


class ClaimConflict(DyslexicError):
    status_code = 409


class AlreadyContacted(DyslexicError):
    status_code = 409


class InvalidOutcome(DyslexicError):
    status_code = 400


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    """SQLite drops tzinfo on round-trip; re-attach before comparing."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def normalize_domain(website: str | None) -> str | None:
    """
    Reduce a website to a comparable domain.

    ``https://www.zomato.com/careers?ref=x`` and ``zomato.com`` both become
    ``zomato.com``, so the same sponsor cannot be added twice under two
    spellings. Subdomains are preserved — ``careers.zomato.com`` is treated as
    distinct, because guessing that it is the same organisation is not safe.
    """
    if not website or not website.strip():
        return None

    candidate = website.strip()
    if "//" not in candidate:
        candidate = f"//{candidate}"

    host = urlsplit(candidate).hostname or ""
    host = host.lower().strip(".")
    if host.startswith("www."):
        host = host[4:]

    return host or None


async def _display_name(db: AsyncSession, user_id: uuid.UUID | None) -> str | None:
    if user_id is None:
        return None
    return await db.scalar(select(User.display_name).where(User.id == user_id))


async def _get_contact(db: AsyncSession, contact_id: uuid.UUID) -> DyslexicContact:
    contact = await db.get(DyslexicContact, contact_id)
    if contact is None:
        raise NotFound("Contact not found.", contact_id=str(contact_id))
    return contact


async def _get_company(db: AsyncSession, company_id: uuid.UUID) -> DyslexicCompany:
    company = await db.get(DyslexicCompany, company_id)
    if company is None:
        raise NotFound("Company not found.", company_id=str(company_id))
    return company


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------

async def record_event(
    db: AsyncSession,
    *,
    company_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    kind: str,
    summary: str,
    contact_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
    audit: bool = True,
) -> DyslexicEvent:
    """
    Append to a company's timeline, and to the platform audit log.

    Both are written because they serve different readers: the timeline is a
    product feature indexed by company, the audit log is a forensic record
    indexed by action. Neither is committed here.
    """
    event = DyslexicEvent(
        company_id=company_id,
        contact_id=contact_id,
        actor_id=actor_id,
        kind=kind,
        summary=summary[:300],
        metadata_json=metadata or {},
    )
    db.add(event)

    if audit:
        await write_audit_entry(
            db,
            actor_id=actor_id,
            action=f"dyslexic.{kind}",
            target_type="dyslexic_company",
            target_id=str(company_id),
            metadata={"summary": summary, "contact_id": str(contact_id) if contact_id else None,
                      **(metadata or {})},
        )

    return event


# ---------------------------------------------------------------------------
# Claims
# ---------------------------------------------------------------------------

async def claim_contact(
    db: AsyncSession, *, contact_id: uuid.UUID, user_id: uuid.UUID
) -> DyslexicContact:
    """
    Take the soft draft claim on a contact for ``CLAIM_MINUTES``.

    A single conditional UPDATE, so two volunteers clicking Generate at the same
    moment cannot both win. Claims lapse on their own — there is no unlock
    button and no cleanup job.
    """
    contact = await _get_contact(db, contact_id)
    now = _now()

    result = await db.execute(
        update(DyslexicContact)
        .where(
            DyslexicContact.id == contact_id,
            (DyslexicContact.claimed_by.is_(None))
            | (DyslexicContact.claimed_by == user_id)
            | (DyslexicContact.claim_expires_at < now),
        )
        .values(
            claimed_by=user_id,
            claimed_at=now,
            claim_expires_at=now + timedelta(minutes=CLAIM_MINUTES),
        )
        # Let the database evaluate the expiry comparison. The ORM's Python-side
        # synchronisation would compare a driver-returned datetime against an
        # aware one, which SQLite makes naive. We refresh explicitly below.
        .execution_options(synchronize_session=False)
    )

    if result.rowcount == 0:
        await db.refresh(contact)
        holder = await _display_name(db, contact.claimed_by)
        expires = _as_utc(contact.claim_expires_at)
        raise ClaimConflict(
            f"{holder or 'Another volunteer'} is drafting an email to this contact.",
            claimed_by=holder,
            claim_expires_at=expires.isoformat() if expires else None,
        )

    await db.refresh(contact)
    return contact


async def release_claim(
    db: AsyncSession, *, contact_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """Drop your own claim. Someone else's claim is left alone."""
    await db.execute(
        update(DyslexicContact)
        .where(
            DyslexicContact.id == contact_id,
            DyslexicContact.claimed_by == user_id,
        )
        .values(claimed_by=None, claimed_at=None, claim_expires_at=None)
    )


async def _clear_claim(db: AsyncSession, contact: DyslexicContact) -> None:
    contact.claimed_by = None
    contact.claimed_at = None
    contact.claim_expires_at = None


# ---------------------------------------------------------------------------
# Follow-ups
# ---------------------------------------------------------------------------

async def _resolve_pending_follow_ups(
    db: AsyncSession, *, contact_id: uuid.UUID, user_id: uuid.UUID | None
) -> None:
    """Close any open follow-up for a contact. Keeps the one-pending invariant."""
    await db.execute(
        update(DyslexicFollowUp)
        .where(
            DyslexicFollowUp.contact_id == contact_id,
            DyslexicFollowUp.status == "pending",
        )
        .values(status="done", resolved_at=_now(), resolved_by=user_id)
    )


async def resolve_follow_up(
    db: AsyncSession,
    *,
    follow_up_id: uuid.UUID,
    user_id: uuid.UUID,
    note: str | None = None,
) -> DyslexicFollowUp:
    """Mark a follow-up handled without logging a send."""
    follow_up = await db.get(DyslexicFollowUp, follow_up_id)
    if follow_up is None:
        raise NotFound("Follow-up not found.", follow_up_id=str(follow_up_id))

    follow_up.status = "done"
    follow_up.resolved_at = _now()
    follow_up.resolved_by = user_id

    await record_event(
        db,
        company_id=follow_up.company_id,
        contact_id=follow_up.contact_id,
        actor_id=user_id,
        kind="follow_up.resolved",
        summary=f"Follow-up marked handled{f': {note}' if note else ''}",
        metadata={"follow_up_id": str(follow_up_id), "note": note},
    )
    return follow_up


# ---------------------------------------------------------------------------
# Outreach
# ---------------------------------------------------------------------------

async def log_send(
    db: AsyncSession,
    *,
    contact_id: uuid.UUID,
    user_id: uuid.UUID,
    kind: str = "initial",
    email_id: uuid.UUID | None = None,
) -> DyslexicOutreach:
    """
    Record that a volunteer sent an email — the "I've Sent Email" click.

    Order matters: the contact is locked first, the duplicate check happens
    against the locked row, and the follow-up is replaced rather than added to.
    Nothing is committed; a failure anywhere leaves no partial record.
    """
    locked = await db.execute(
        select(DyslexicContact)
        .where(DyslexicContact.id == contact_id)
        .with_for_update()
    )
    contact = locked.scalar_one_or_none()
    if contact is None:
        raise NotFound("Contact not found.", contact_id=str(contact_id))

    if kind == "initial" and contact.contacted_at is not None:
        holder = await _display_name(db, contact.contacted_by)
        when = _as_utc(contact.contacted_at)
        pretty = when.strftime("%-d %b %Y") if when else "earlier"
        raise AlreadyContacted(
            f"{holder or 'Another volunteer'} already emailed this contact on {pretty}.",
            contacted_by=holder,
            contacted_at=when.isoformat() if when else None,
        )

    company = await _get_company(db, contact.company_id)
    now = _now()

    outreach = DyslexicOutreach(
        contact_id=contact.id,
        company_id=company.id,
        email_id=email_id,
        kind=kind,
        sent_by=user_id,
        sent_at=now,
    )
    db.add(outreach)
    await db.flush()

    if kind == "initial":
        contact.contacted_by = user_id
        contact.contacted_at = now
        contact.status = "contacted"

    company.stage = advance_stage(
        company.stage, "email_sent" if kind == "initial" else "follow_up"
    )

    # Replace, never accumulate.
    await _resolve_pending_follow_ups(db, contact_id=contact.id, user_id=user_id)
    db.add(
        DyslexicFollowUp(
            outreach_id=outreach.id,
            contact_id=contact.id,
            company_id=company.id,
            assigned_to=user_id,
            due_at=now + timedelta(days=FOLLOW_UP_INTERVAL_DAYS),
        )
    )

    await _clear_claim(db, contact)

    actor = await _display_name(db, user_id) or "A volunteer"
    verb = "Email sent" if kind == "initial" else "Follow-up sent"
    await record_event(
        db,
        company_id=company.id,
        contact_id=contact.id,
        actor_id=user_id,
        kind="email.sent" if kind == "initial" else "follow_up.sent",
        summary=f"{verb} to {contact.name} by {actor}",
        metadata={"outreach_id": str(outreach.id), "kind": kind},
    )

    return outreach


async def record_outcome(
    db: AsyncSession,
    *,
    outreach_id: uuid.UUID,
    user_id: uuid.UUID,
    outcome: str,
    note: str | None = None,
    email_id: uuid.UUID | None = None,
) -> DyslexicOutreach:
    """
    Record what came back, three days later.

    ``follow_up_sent`` delegates to :func:`log_send` rather than duplicating its
    logic, so a chase logged this way is indistinguishable from one logged
    through the send route — including the follow-up bookkeeping.
    """
    if outcome not in OUTREACH_OUTCOMES:
        raise InvalidOutcome(
            f"Unknown outcome '{outcome}'.", allowed=list(OUTREACH_OUTCOMES)
        )

    outreach = await db.get(DyslexicOutreach, outreach_id)
    if outreach is None:
        raise NotFound("Outreach record not found.", outreach_id=str(outreach_id))

    contact = await _get_contact(db, outreach.contact_id)
    company = await _get_company(db, outreach.company_id)

    outreach.outcome = outcome
    outreach.outcome_at = _now()
    outreach.outcome_by = user_id
    outreach.outcome_note = note

    new_status = OUTCOME_CONTACT_STATUS_MAP.get(outcome)
    if new_status:
        contact.status = new_status

    new_stage = OUTCOME_STAGE_MAP.get(outcome)
    if new_stage:
        company.stage = advance_stage(company.stage, new_stage)

    actor = await _display_name(db, user_id) or "A volunteer"
    await record_event(
        db,
        company_id=company.id,
        contact_id=contact.id,
        actor_id=user_id,
        kind="outcome.recorded",
        summary=f"{contact.name}: {outcome.replace('_', ' ')} — recorded by {actor}",
        metadata={"outreach_id": str(outreach_id), "outcome": outcome, "note": note},
    )

    if outcome == "follow_up_sent":
        # Opens the next follow-up and closes this one, in one place.
        await log_send(
            db,
            contact_id=contact.id,
            user_id=user_id,
            kind="follow_up",
            email_id=email_id,
        )
    else:
        await _resolve_pending_follow_ups(
            db, contact_id=contact.id, user_id=user_id
        )

    return outreach
