"""
Dyslexic router — sponsorship and outreach.

**Access is open to every logged-in member.** There are no ``dyslexic.*``
permission keys and no grants to check; a valid signed session from the Next.js
proxy is the whole gate. Outreach is volunteer-driven and gating it would slow
down the people it exists to help.

Two things carry the safety that permissions would otherwise provide:

* nothing is hard-deleted — companies and contacts archive, and no DELETE route
  exists for either, and
* every mutation is attributed, writing both a timeline event and an audit entry.

Handlers stay thin: they validate, delegate to :mod:`app.dyslexic.service` for
anything transactional, commit, and only then publish to the event bus.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    DyslexicCompany,
    DyslexicContact,
    DyslexicEmail,
    DyslexicEvent,
    DyslexicFollowUp,
    DyslexicOutreach,
    User,
)
from app.dependencies import CurrentUserDep, DbSession
from app.dyslexic import service
from app.dyslexic.research import run_research_task
from app.dyslexic.stats import dashboard_stats, leaderboard
from app.events import event_bus
from app.schemas.dyslexic import (
    CompanyCreate,
    CompanyDetailOut,
    CompanyOut,
    CompanyUpdate,
    ContactCreate,
    ContactCreateOut,
    ContactOut,
    ContactUpdate,
    EventOut,
    FollowUpOut,
    FollowUpResolveIn,
    LeaderboardRowOut,
    OutcomeIn,
    OutreachOut,
    SendIn,
    StatsOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dyslexic", tags=["dyslexic"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _raise(error: service.DyslexicError) -> None:
    """Translate a workflow error into its HTTP equivalent, detail intact."""
    raise HTTPException(status_code=error.status_code, detail=error.detail)


async def _publish(event_type: str, payload: dict[str, Any]) -> None:
    """
    Announce a change to other connected volunteers.

    Called only after a successful commit — publishing earlier would advertise
    state that might roll back. A broker failure must not fail the request that
    already succeeded, so this never raises.
    """
    try:
        await event_bus.publish(event_type, payload)
    except Exception:  # pragma: no cover - broker failures are non-fatal
        logger.warning("Failed to publish %s", event_type, exc_info=True)


async def _name_map(db: AsyncSession, user_ids: set[uuid.UUID | None]) -> dict:
    """Resolve display names in one query instead of per row."""
    ids = {uid for uid in user_ids if uid}
    if not ids:
        return {}
    rows = await db.execute(
        select(User.id, User.display_name, User.avatar_url).where(User.id.in_(ids))
    )
    return {row.id: (row.display_name, row.avatar_url) for row in rows}


async def _company_out(db: AsyncSession, company: DyslexicCompany) -> CompanyOut:
    contact_count = await db.scalar(
        select(func.count())
        .select_from(DyslexicContact)
        .where(
            DyslexicContact.company_id == company.id,
            DyslexicContact.is_archived.is_(False),
        )
    )
    names = await _name_map(db, {company.added_by})
    payload = CompanyOut.model_validate(company)
    payload.contact_count = contact_count or 0
    payload.added_by_name = names.get(company.added_by, (None, None))[0]
    return payload


async def _contact_out(
    db: AsyncSession, contact: DyslexicContact, *, company_name: str | None = None
) -> ContactOut:
    names = await _name_map(db, {contact.contacted_by, contact.claimed_by})
    payload = ContactOut.model_validate(contact)
    payload.contacted_by_name = names.get(contact.contacted_by, (None, None))[0]
    payload.claimed_by_name = names.get(contact.claimed_by, (None, None))[0]
    payload.company_name = company_name
    return payload


async def _events_out(
    db: AsyncSession, events: list[DyslexicEvent], *, with_company: bool = False
) -> list[EventOut]:
    names = await _name_map(db, {event.actor_id for event in events})
    company_names: dict[uuid.UUID, str] = {}
    if with_company and events:
        rows = await db.execute(
            select(DyslexicCompany.id, DyslexicCompany.name).where(
                DyslexicCompany.id.in_({event.company_id for event in events})
            )
        )
        company_names = {row.id: row.name for row in rows}

    out = []
    for event in events:
        payload = EventOut.model_validate(event)
        actor = names.get(event.actor_id, (None, None))
        payload.actor_name = actor[0]
        payload.actor_avatar = actor[1]
        payload.company_name = company_names.get(event.company_id)
        out.append(payload)
    return out


async def _get_company_or_404(db: AsyncSession, company_id: uuid.UUID) -> DyslexicCompany:
    company = await db.get(DyslexicCompany, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found.")
    return company


async def _get_contact_or_404(db: AsyncSession, contact_id: uuid.UUID) -> DyslexicContact:
    contact = await db.get(DyslexicContact, contact_id)
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found.")
    return contact


# ---------------------------------------------------------------------------
# Dashboard, activity, leaderboard
# ---------------------------------------------------------------------------

@router.get("/stats", response_model=StatsOut)
async def get_stats(db: DbSession, current_user: CurrentUserDep) -> StatsOut:
    """The dashboard tiles, including this volunteer's own overdue count."""
    return StatsOut(**await dashboard_stats(db, current_user.user_id))


@router.get("/activity", response_model=list[EventOut])
async def get_activity(
    db: DbSession,
    current_user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[EventOut]:
    """What everyone has been doing, newest first."""
    events = (
        await db.execute(
            select(DyslexicEvent)
            .order_by(DyslexicEvent.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return await _events_out(db, list(events), with_company=True)


@router.get("/leaderboard", response_model=list[LeaderboardRowOut])
async def get_leaderboard(
    db: DbSession,
    current_user: CurrentUserDep,
    period: Annotated[str, Query(pattern="^(all|30d)$")] = "all",
) -> list[LeaderboardRowOut]:
    """Volunteer contributions, ranked. Outcomes weigh more than volume."""
    rows = await leaderboard(db, period=period)
    return [LeaderboardRowOut(**row) for row in rows]


# ---------------------------------------------------------------------------
# Companies
# ---------------------------------------------------------------------------

@router.get("/companies", response_model=list[CompanyOut])
async def list_companies(
    db: DbSession,
    current_user: CurrentUserDep,
    stage: Annotated[str | None, Query()] = None,
    q: Annotated[str | None, Query()] = None,
    fork_id: Annotated[uuid.UUID | None, Query()] = None,
    archived: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[CompanyOut]:
    """List sponsor prospects, newest first."""
    stmt = select(DyslexicCompany).where(DyslexicCompany.is_archived.is_(archived))
    if stage:
        stmt = stmt.where(DyslexicCompany.stage == stage)
    if fork_id:
        stmt = stmt.where(DyslexicCompany.fork_id == fork_id)
    if q:
        pattern = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(DyslexicCompany.name).like(pattern),
                func.lower(DyslexicCompany.normalized_domain).like(pattern),
            )
        )
    stmt = stmt.order_by(DyslexicCompany.created_at.desc()).limit(limit).offset(offset)

    companies = (await db.execute(stmt)).scalars().all()
    return [await _company_out(db, company) for company in companies]


@router.post("/companies", response_model=CompanyOut, status_code=status.HTTP_201_CREATED)
async def create_company(
    payload: CompanyCreate,
    db: DbSession,
    current_user: CurrentUserDep,
    background_tasks: BackgroundTasks,
) -> CompanyOut:
    """
    Add a sponsor prospect from just a name and a website.

    Duplicates are refused with the existing record attached, so the second
    volunteer gets a link rather than a dead end. Research runs in the
    background — a ten-second model call must not hold up the request.
    """
    domain = service.normalize_domain(payload.website)
    name = payload.name.strip()

    if domain:
        existing = await db.scalar(
            select(DyslexicCompany).where(DyslexicCompany.normalized_domain == domain)
        )
    else:
        # No website means no domain to compare, and NULLs never collide — fall
        # back to the name so one sponsor cannot become two records.
        existing = await db.scalar(
            select(DyslexicCompany).where(
                func.lower(DyslexicCompany.name) == name.lower(),
                DyslexicCompany.is_archived.is_(False),
            )
        )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": f"{existing.name} is already being tracked.",
                "existing_company_id": str(existing.id),
                "existing_company_name": existing.name,
            },
        )

    company = DyslexicCompany(
        name=name,
        website=payload.website.strip() if payload.website else None,
        normalized_domain=domain,
        fork_id=payload.fork_id,
        notes=payload.notes,
        added_by=current_user.user_id,
    )
    db.add(company)
    await db.flush()

    actor = await db.scalar(
        select(User.display_name).where(User.id == current_user.user_id)
    )
    await service.record_event(
        db,
        company_id=company.id,
        actor_id=current_user.user_id,
        kind="company.added",
        summary=f"{name} added by {actor or 'a volunteer'}",
        metadata={"website": company.website},
    )
    await db.commit()
    await db.refresh(company)

    await _publish(
        "dyslexic.company.created",
        {"company_id": str(company.id), "name": company.name},
    )
    background_tasks.add_task(run_research_task, company.id)

    return await _company_out(db, company)


@router.get("/companies/{company_id}", response_model=CompanyDetailOut)
async def get_company(
    company_id: uuid.UUID, db: DbSession, current_user: CurrentUserDep
) -> CompanyDetailOut:
    """Everything the company page renders, in one round-trip."""
    company = await _get_company_or_404(db, company_id)

    contacts = (
        await db.execute(
            select(DyslexicContact)
            .where(
                DyslexicContact.company_id == company_id,
                DyslexicContact.is_archived.is_(False),
            )
            .order_by(DyslexicContact.created_at.asc())
        )
    ).scalars().all()

    events = (
        await db.execute(
            select(DyslexicEvent)
            .where(DyslexicEvent.company_id == company_id)
            .order_by(DyslexicEvent.created_at.desc())
            .limit(50)
        )
    ).scalars().all()

    base = await _company_out(db, company)
    detail = CompanyDetailOut(**base.model_dump())
    detail.contacts = [await _contact_out(db, contact) for contact in contacts]
    detail.timeline = await _events_out(db, list(events))
    return detail


@router.patch("/companies/{company_id}", response_model=CompanyOut)
async def update_company(
    company_id: uuid.UUID,
    payload: CompanyUpdate,
    db: DbSession,
    current_user: CurrentUserDep,
) -> CompanyOut:
    """
    Edit a company, including a manual stage correction.

    ``negotiation`` has no automatic trigger, so this is also how a company
    reaches it. Manual stage edits bypass the monotonic rule deliberately —
    correcting a mistake has to be possible in both directions.
    """
    company = await _get_company_or_404(db, company_id)
    changes = payload.model_dump(exclude_unset=True)

    if "website" in changes:
        changes["normalized_domain"] = service.normalize_domain(changes["website"])

    previous_stage = company.stage
    for field, value in changes.items():
        setattr(company, field, value)

    if changes.get("stage") and changes["stage"] != previous_stage:
        await service.record_event(
            db,
            company_id=company.id,
            actor_id=current_user.user_id,
            kind="stage.changed",
            summary=f"Stage changed from {previous_stage} to {changes['stage']}",
            metadata={"from": previous_stage, "to": changes["stage"]},
        )

    if changes.get("is_archived") is True:
        await service.record_event(
            db,
            company_id=company.id,
            actor_id=current_user.user_id,
            kind="company.archived",
            summary=f"{company.name} archived",
        )

    await db.commit()
    await db.refresh(company)

    await _publish(
        "dyslexic.company.updated",
        {"company_id": str(company.id), "name": company.name},
    )
    return await _company_out(db, company)


@router.get("/companies/{company_id}/timeline", response_model=list[EventOut])
async def company_timeline(
    company_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[EventOut]:
    """Who did what to this company, newest first."""
    await _get_company_or_404(db, company_id)
    events = (
        await db.execute(
            select(DyslexicEvent)
            .where(DyslexicEvent.company_id == company_id)
            .order_by(DyslexicEvent.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return await _events_out(db, list(events))


@router.post("/companies/{company_id}/research", status_code=status.HTTP_202_ACCEPTED)
async def rerun_research(
    company_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUserDep,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """Re-run AI research — the Retry behind a failed research panel."""
    company = await _get_company_or_404(db, company_id)
    company.research_status = "pending"
    company.research_error = None
    await db.commit()

    background_tasks.add_task(run_research_task, company_id)
    return {"status": "pending", "company_id": str(company_id)}


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------

@router.get("/contacts", response_model=list[ContactOut])
async def list_contacts(
    db: DbSession,
    current_user: CurrentUserDep,
    company_id: Annotated[uuid.UUID | None, Query()] = None,
    contact_status: Annotated[str | None, Query(alias="status")] = None,
    q: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ContactOut]:
    """Contacts across every company — the 'who still needs an email' view."""
    stmt = (
        select(DyslexicContact, DyslexicCompany.name)
        .join(DyslexicCompany, DyslexicCompany.id == DyslexicContact.company_id)
        .where(DyslexicContact.is_archived.is_(False))
    )
    if company_id:
        stmt = stmt.where(DyslexicContact.company_id == company_id)
    if contact_status:
        stmt = stmt.where(DyslexicContact.status == contact_status)
    if q:
        pattern = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(DyslexicContact.name).like(pattern),
                func.lower(DyslexicContact.email).like(pattern),
                func.lower(DyslexicCompany.name).like(pattern),
            )
        )
    stmt = stmt.order_by(DyslexicContact.created_at.desc()).limit(limit).offset(offset)

    rows = (await db.execute(stmt)).all()
    return [
        await _contact_out(db, contact, company_name=company_name)
        for contact, company_name in rows
    ]


@router.post(
    "/companies/{company_id}/contacts",
    response_model=ContactCreateOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_contact(
    company_id: uuid.UUID,
    payload: ContactCreate,
    db: DbSession,
    current_user: CurrentUserDep,
) -> ContactCreateOut:
    """
    Add someone to contact at this company.

    The same address at another company is allowed — people change jobs — but
    the response says so, making it a decision rather than an accident.
    """
    company = await _get_company_or_404(db, company_id)
    email = payload.email.strip().lower() if payload.email else None

    if email:
        clash = await db.scalar(
            select(DyslexicContact).where(
                DyslexicContact.company_id == company_id,
                DyslexicContact.email == email,
            )
        )
        if clash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": f"{clash.name} already has this email at {company.name}.",
                    "existing_contact_id": str(clash.id),
                },
            )

    warning = None
    if email:
        elsewhere = (
            await db.execute(
                select(DyslexicCompany.name)
                .join(DyslexicContact, DyslexicContact.company_id == DyslexicCompany.id)
                .where(
                    DyslexicContact.email == email,
                    DyslexicContact.company_id != company_id,
                )
                .limit(3)
            )
        ).scalars().all()
        if elsewhere:
            warning = (
                f"This email is also listed at {', '.join(elsewhere)}. "
                "Check you are not duplicating outreach."
            )

    contact = DyslexicContact(
        company_id=company_id,
        name=payload.name.strip(),
        role=payload.role,
        email=email,
        linkedin_url=payload.linkedin_url,
        notes=payload.notes,
        added_by=current_user.user_id,
    )
    db.add(contact)
    await db.flush()

    company.stage = service.advance_stage(company.stage, "contacts_added")

    actor = await db.scalar(
        select(User.display_name).where(User.id == current_user.user_id)
    )
    await service.record_event(
        db,
        company_id=company_id,
        contact_id=contact.id,
        actor_id=current_user.user_id,
        kind="contact.added",
        summary=f"{contact.name} added by {actor or 'a volunteer'}",
        metadata={"role": contact.role},
    )
    await db.commit()
    await db.refresh(contact)

    await _publish(
        "dyslexic.contact.created",
        {"company_id": str(company_id), "contact_id": str(contact.id)},
    )

    base = await _contact_out(db, contact, company_name=company.name)
    out = ContactCreateOut(**base.model_dump())
    out.duplicate_warning = warning
    return out


@router.patch("/contacts/{contact_id}", response_model=ContactOut)
async def update_contact(
    contact_id: uuid.UUID,
    payload: ContactUpdate,
    db: DbSession,
    current_user: CurrentUserDep,
) -> ContactOut:
    """Edit a contact, including archiving them."""
    contact = await _get_contact_or_404(db, contact_id)
    changes = payload.model_dump(exclude_unset=True)

    if "email" in changes and changes["email"]:
        changes["email"] = changes["email"].strip().lower()

    for field, value in changes.items():
        setattr(contact, field, value)

    await service.record_event(
        db,
        company_id=contact.company_id,
        contact_id=contact.id,
        actor_id=current_user.user_id,
        kind="contact.updated",
        summary=f"{contact.name} updated",
        metadata={"fields": sorted(changes.keys())},
    )
    await db.commit()
    await db.refresh(contact)

    await _publish(
        "dyslexic.contact.updated",
        {"company_id": str(contact.company_id), "contact_id": str(contact.id)},
    )
    return await _contact_out(db, contact)


@router.post("/contacts/{contact_id}/claim", response_model=ContactOut)
async def claim_contact(
    contact_id: uuid.UUID, db: DbSession, current_user: CurrentUserDep
) -> ContactOut:
    """
    Signal that you are drafting an email to this contact.

    A soft claim, visible to everyone, so two volunteers do not write the same
    email in parallel. It lapses on its own; there is no unlock button.
    """
    try:
        contact = await service.claim_contact(
            db, contact_id=contact_id, user_id=current_user.user_id
        )
    except service.DyslexicError as error:
        await db.rollback()
        _raise(error)

    await db.commit()
    await db.refresh(contact)

    await _publish(
        "dyslexic.contact.claimed",
        {"company_id": str(contact.company_id), "contact_id": str(contact.id)},
    )
    return await _contact_out(db, contact)


@router.delete("/contacts/{contact_id}/claim", status_code=status.HTTP_204_NO_CONTENT)
async def release_contact_claim(
    contact_id: uuid.UUID, db: DbSession, current_user: CurrentUserDep
) -> None:
    """Give up your claim — someone else's is left alone."""
    contact = await _get_contact_or_404(db, contact_id)
    await service.release_claim(
        db, contact_id=contact_id, user_id=current_user.user_id
    )
    await db.commit()

    await _publish(
        "dyslexic.contact.released",
        {"company_id": str(contact.company_id), "contact_id": str(contact_id)},
    )


# ---------------------------------------------------------------------------
# Outreach
# ---------------------------------------------------------------------------

@router.post(
    "/contacts/{contact_id}/sent",
    response_model=OutreachOut,
    status_code=status.HTTP_201_CREATED,
)
async def mark_sent(
    contact_id: uuid.UUID,
    payload: SendIn,
    db: DbSession,
    current_user: CurrentUserDep,
) -> OutreachOut:
    """
    The "I've Sent Email" click.

    One transaction records the send, marks the contact contacted, advances the
    company, and replaces the follow-up. A second initial send is refused with
    the name of whoever got there first.
    """
    try:
        outreach = await service.log_send(
            db,
            contact_id=contact_id,
            user_id=current_user.user_id,
            kind=payload.kind,
            email_id=payload.email_id,
        )
    except service.DyslexicError as error:
        await db.rollback()
        _raise(error)

    await db.commit()
    await db.refresh(outreach)

    await _publish(
        "dyslexic.email.sent",
        {
            "company_id": str(outreach.company_id),
            "contact_id": str(outreach.contact_id),
            "kind": outreach.kind,
        },
    )

    names = await _name_map(db, {outreach.sent_by})
    out = OutreachOut.model_validate(outreach)
    out.sent_by_name = names.get(outreach.sent_by, (None, None))[0]
    return out


@router.patch("/outreach/{outreach_id}/outcome", response_model=OutreachOut)
async def record_outcome(
    outreach_id: uuid.UUID,
    payload: OutcomeIn,
    db: DbSession,
    current_user: CurrentUserDep,
) -> OutreachOut:
    """Record what came back — the day-three update."""
    try:
        outreach = await service.record_outcome(
            db,
            outreach_id=outreach_id,
            user_id=current_user.user_id,
            outcome=payload.outcome,
            note=payload.note,
        )
    except service.DyslexicError as error:
        await db.rollback()
        _raise(error)

    await db.commit()
    await db.refresh(outreach)

    await _publish(
        "dyslexic.outcome.recorded",
        {
            "company_id": str(outreach.company_id),
            "contact_id": str(outreach.contact_id),
            "outcome": outreach.outcome,
        },
    )

    names = await _name_map(db, {outreach.sent_by})
    out = OutreachOut.model_validate(outreach)
    out.sent_by_name = names.get(outreach.sent_by, (None, None))[0]
    return out


@router.get("/contacts/{contact_id}/outreach", response_model=list[OutreachOut])
async def list_contact_outreach(
    contact_id: uuid.UUID, db: DbSession, current_user: CurrentUserDep
) -> list[OutreachOut]:
    """Everything ever sent to this contact, newest first."""
    await _get_contact_or_404(db, contact_id)
    rows = (
        await db.execute(
            select(DyslexicOutreach)
            .where(DyslexicOutreach.contact_id == contact_id)
            .order_by(DyslexicOutreach.sent_at.desc())
        )
    ).scalars().all()

    names = await _name_map(db, {row.sent_by for row in rows})
    out = []
    for row in rows:
        payload = OutreachOut.model_validate(row)
        payload.sent_by_name = names.get(row.sent_by, (None, None))[0]
        out.append(payload)
    return out


# ---------------------------------------------------------------------------
# Follow-ups
# ---------------------------------------------------------------------------

@router.get("/follow-ups", response_model=list[FollowUpOut])
async def list_follow_ups(
    db: DbSession,
    current_user: CurrentUserDep,
    scope: Annotated[str, Query(pattern="^(mine|all)$")] = "mine",
    follow_up_status: Annotated[str, Query(alias="status")] = "pending",
    overdue: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[FollowUpOut]:
    """What needs chasing — yours by default."""
    now = datetime.now(timezone.utc)

    stmt = (
        select(DyslexicFollowUp, DyslexicContact.name, DyslexicCompany.name)
        .join(DyslexicContact, DyslexicContact.id == DyslexicFollowUp.contact_id)
        .join(DyslexicCompany, DyslexicCompany.id == DyslexicFollowUp.company_id)
        .where(DyslexicFollowUp.status == follow_up_status)
    )
    if scope == "mine":
        stmt = stmt.where(DyslexicFollowUp.assigned_to == current_user.user_id)
    if overdue:
        stmt = stmt.where(DyslexicFollowUp.due_at < now)
    stmt = stmt.order_by(DyslexicFollowUp.due_at.asc()).limit(limit)

    rows = (await db.execute(stmt)).all()
    names = await _name_map(db, {row[0].assigned_to for row in rows})

    out = []
    for follow_up, contact_name, company_name in rows:
        payload = FollowUpOut.model_validate(follow_up)
        payload.contact_name = contact_name
        payload.company_name = company_name
        payload.assigned_to_name = names.get(follow_up.assigned_to, (None, None))[0]
        due = follow_up.due_at
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        payload.is_overdue = follow_up.status == "pending" and due < now
        out.append(payload)
    return out


@router.post("/follow-ups/{follow_up_id}/resolve", response_model=FollowUpOut)
async def resolve_follow_up(
    follow_up_id: uuid.UUID,
    payload: FollowUpResolveIn,
    db: DbSession,
    current_user: CurrentUserDep,
) -> FollowUpOut:
    """Mark a follow-up handled without logging a send."""
    try:
        follow_up = await service.resolve_follow_up(
            db,
            follow_up_id=follow_up_id,
            user_id=current_user.user_id,
            note=payload.note,
        )
    except service.DyslexicError as error:
        await db.rollback()
        _raise(error)

    await db.commit()
    await db.refresh(follow_up)

    await _publish(
        "dyslexic.follow_up.resolved",
        {
            "company_id": str(follow_up.company_id),
            "follow_up_id": str(follow_up.id),
        },
    )
    return FollowUpOut.model_validate(follow_up)
