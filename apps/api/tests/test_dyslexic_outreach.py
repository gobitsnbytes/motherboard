"""
The guarantees Dyslexic exists to provide.

Two volunteers must never both send an initial email to the same contact, a
contact must never accumulate two pending follow-ups, and a company's pipeline
stage must never move backwards. These are tested at the service layer, where
the transactions are, rather than through HTTP.
"""

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    DyslexicCompany,
    DyslexicContact,
    DyslexicFollowUp,
    DyslexicEvent,
    DyslexicOutreach,
    User,
)
from app.dyslexic import service
from app.dyslexic.constants import FOLLOW_UP_INTERVAL_DAYS


def as_utc(value: datetime) -> datetime:
    """SQLite drops tzinfo on round-trip; normalise before comparing."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


@pytest_asyncio.fixture
async def world(db_session: AsyncSession):
    """Two volunteers, one company, two contacts."""
    priya = User(display_name="Priya", email="priya@bnb.org")
    aarav = User(display_name="Aarav", email="aarav@bnb.org")
    db_session.add_all([priya, aarav])
    await db_session.flush()

    company = DyslexicCompany(
        name="Zomato",
        website="https://zomato.com",
        normalized_domain="zomato.com",
        added_by=priya.id,
    )
    db_session.add(company)
    await db_session.flush()

    first = DyslexicContact(
        company_id=company.id, name="Dev Rel Lead",
        email="devrel@zomato.com", added_by=priya.id,
    )
    second = DyslexicContact(
        company_id=company.id, name="Campus Marketing",
        email="campus@zomato.com", added_by=priya.id,
    )
    db_session.add_all([first, second])
    await db_session.commit()

    return {
        "priya": priya, "aarav": aarav, "company": company,
        "first": first, "second": second,
    }


async def count(db: AsyncSession, model, **filters) -> int:
    stmt = select(func.count()).select_from(model)
    for field, value in filters.items():
        stmt = stmt.where(getattr(model, field) == value)
    return (await db.execute(stmt)).scalar_one()


# ---------------------------------------------------------------------------
# normalize_domain
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "website,expected",
    [
        ("https://zomato.com", "zomato.com"),
        ("https://www.zomato.com/careers?ref=x", "zomato.com"),
        ("http://WWW.Zomato.COM/", "zomato.com"),
        ("zomato.com", "zomato.com"),
        ("  https://zomato.com/  ", "zomato.com"),
        ("https://careers.zomato.com", "careers.zomato.com"),
        (None, None),
        ("", None),
        ("   ", None),
    ],
)
def test_normalize_domain(website, expected):
    """Every spelling of the same site collapses to one comparable domain."""
    assert service.normalize_domain(website) == expected


# ---------------------------------------------------------------------------
# log_send
# ---------------------------------------------------------------------------

async def test_log_send_creates_outreach_contact_state_and_follow_up(
    db_session: AsyncSession, world
):
    contact, priya, company = world["first"], world["priya"], world["company"]

    outreach = await service.log_send(
        db_session, contact_id=contact.id, user_id=priya.id, kind="initial"
    )
    await db_session.commit()

    assert outreach.kind == "initial"
    assert outreach.sent_by == priya.id
    assert await count(db_session, DyslexicOutreach, contact_id=contact.id) == 1

    await db_session.refresh(contact)
    assert contact.contacted_by == priya.id
    assert contact.contacted_at is not None
    assert contact.status == "contacted"

    await db_session.refresh(company)
    assert company.stage == "email_sent"

    follow_ups = (
        await db_session.execute(
            select(DyslexicFollowUp).where(DyslexicFollowUp.contact_id == contact.id)
        )
    ).scalars().all()
    assert len(follow_ups) == 1
    assert follow_ups[0].status == "pending"
    assert follow_ups[0].assigned_to == priya.id
    delta = as_utc(follow_ups[0].due_at) - as_utc(outreach.sent_at)
    assert abs(delta - timedelta(days=FOLLOW_UP_INTERVAL_DAYS)) < timedelta(seconds=5)

    events = (
        await db_session.execute(
            select(DyslexicEvent).where(DyslexicEvent.kind == "email.sent")
        )
    ).scalars().all()
    assert len(events) == 1
    assert events[0].actor_id == priya.id


async def test_second_initial_send_raises_already_contacted(
    db_session: AsyncSession, world
):
    """The whole point of the module: no two volunteers email the same person."""
    contact, priya, aarav = world["first"], world["priya"], world["aarav"]
    contact_id = contact.id  # captured before the rollback below expires it

    await service.log_send(
        db_session, contact_id=contact.id, user_id=priya.id, kind="initial"
    )
    await db_session.commit()

    with pytest.raises(service.AlreadyContacted) as excinfo:
        await service.log_send(
            db_session, contact_id=contact.id, user_id=aarav.id, kind="initial"
        )
    await db_session.rollback()

    # The message has to name who and when, or the second volunteer learns nothing.
    assert "Priya" in excinfo.value.detail["message"]
    assert excinfo.value.detail["contacted_by"] == "Priya"
    assert excinfo.value.detail["contacted_at"] is not None
    assert await count(db_session, DyslexicOutreach, contact_id=contact_id) == 1


async def test_claim_is_released_by_log_send(db_session: AsyncSession, world):
    contact, priya = world["first"], world["priya"]

    await service.claim_contact(db_session, contact_id=contact.id, user_id=priya.id)
    await db_session.commit()
    await db_session.refresh(contact)
    assert contact.claimed_by == priya.id

    await service.log_send(
        db_session, contact_id=contact.id, user_id=priya.id, kind="initial"
    )
    await db_session.commit()
    await db_session.refresh(contact)
    assert contact.claimed_by is None
    assert contact.claim_expires_at is None


async def test_follow_up_send_resolves_the_previous_follow_up(
    db_session: AsyncSession, world
):
    """A contact never accumulates two open follow-ups."""
    contact, priya = world["first"], world["priya"]

    await service.log_send(
        db_session, contact_id=contact.id, user_id=priya.id, kind="initial"
    )
    await db_session.commit()

    await service.log_send(
        db_session, contact_id=contact.id, user_id=priya.id, kind="follow_up"
    )
    await db_session.commit()

    assert await count(db_session, DyslexicFollowUp, contact_id=contact.id, status="pending") == 1
    assert await count(db_session, DyslexicFollowUp, contact_id=contact.id, status="done") == 1
    assert await count(db_session, DyslexicOutreach, contact_id=contact.id) == 2

    await db_session.refresh(world["company"])
    assert world["company"].stage == "follow_up"


# ---------------------------------------------------------------------------
# record_outcome
# ---------------------------------------------------------------------------

async def test_record_outcome_follow_up_sent_matches_log_send_path(
    db_session: AsyncSession, world
):
    """
    Both ways of logging a chase converge on identical state — otherwise a
    contact ends up with two pending follow-ups depending on which button the
    volunteer happened to press.
    """
    contact, priya = world["first"], world["priya"]

    initial = await service.log_send(
        db_session, contact_id=contact.id, user_id=priya.id, kind="initial"
    )
    await db_session.commit()

    await service.record_outcome(
        db_session, outreach_id=initial.id, user_id=priya.id, outcome="follow_up_sent"
    )
    await db_session.commit()

    await db_session.refresh(initial)
    assert initial.outcome == "follow_up_sent"
    assert initial.outcome_by == priya.id

    assert await count(db_session, DyslexicOutreach, contact_id=contact.id, kind="follow_up") == 1
    assert await count(db_session, DyslexicFollowUp, contact_id=contact.id, status="pending") == 1
    assert await count(db_session, DyslexicFollowUp, contact_id=contact.id, status="done") == 1


async def test_record_outcome_replied_resolves_follow_up_and_advances_stage(
    db_session: AsyncSession, world
):
    contact, priya, company = world["first"], world["priya"], world["company"]

    outreach = await service.log_send(
        db_session, contact_id=contact.id, user_id=priya.id, kind="initial"
    )
    await db_session.commit()

    await service.record_outcome(
        db_session, outreach_id=outreach.id, user_id=priya.id,
        outcome="replied", note="Asked for the deck",
    )
    await db_session.commit()

    await db_session.refresh(contact)
    await db_session.refresh(company)
    assert contact.status == "replied"
    assert company.stage == "replied"
    assert await count(db_session, DyslexicFollowUp, contact_id=contact.id, status="pending") == 0


async def test_record_outcome_rejects_unknown_outcome(db_session: AsyncSession, world):
    outreach = await service.log_send(
        db_session, contact_id=world["first"].id,
        user_id=world["priya"].id, kind="initial",
    )
    await db_session.commit()

    with pytest.raises(service.InvalidOutcome):
        await service.record_outcome(
            db_session, outreach_id=outreach.id,
            user_id=world["priya"].id, outcome="ghosted_us",
        )


# ---------------------------------------------------------------------------
# Stage monotonicity
# ---------------------------------------------------------------------------

async def test_stage_never_moves_backwards(db_session: AsyncSession, world):
    """
    A company deep in negotiation must not be dragged back to `email_sent`
    because someone started on a second contact there.
    """
    company, first, second = world["company"], world["first"], world["second"]
    priya = world["priya"]

    outreach = await service.log_send(
        db_session, contact_id=first.id, user_id=priya.id, kind="initial"
    )
    await service.record_outcome(
        db_session, outreach_id=outreach.id, user_id=priya.id,
        outcome="meeting_scheduled",
    )
    await db_session.commit()
    await db_session.refresh(company)
    assert company.stage == "meeting"

    await service.log_send(
        db_session, contact_id=second.id, user_id=priya.id, kind="initial"
    )
    await db_session.commit()
    await db_session.refresh(company)
    assert company.stage == "meeting"


# ---------------------------------------------------------------------------
# Claims
# ---------------------------------------------------------------------------

async def test_claim_conflict_and_expiry(db_session: AsyncSession, world):
    contact, priya, aarav = world["first"], world["priya"], world["aarav"]

    await service.claim_contact(db_session, contact_id=contact.id, user_id=priya.id)
    await db_session.commit()

    with pytest.raises(service.ClaimConflict) as excinfo:
        await service.claim_contact(db_session, contact_id=contact.id, user_id=aarav.id)
    assert excinfo.value.detail["claimed_by"] == "Priya"

    # Re-claiming your own contact extends the window rather than conflicting.
    await service.claim_contact(db_session, contact_id=contact.id, user_id=priya.id)
    await db_session.commit()

    # Once the window lapses the contact is free again, with no cleanup job.
    contact.claim_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    await db_session.commit()

    await service.claim_contact(db_session, contact_id=contact.id, user_id=aarav.id)
    await db_session.commit()
    await db_session.refresh(contact)
    assert contact.claimed_by == aarav.id


async def test_release_claim_only_affects_your_own(db_session: AsyncSession, world):
    contact, priya, aarav = world["first"], world["priya"], world["aarav"]

    await service.claim_contact(db_session, contact_id=contact.id, user_id=priya.id)
    await db_session.commit()

    await service.release_claim(db_session, contact_id=contact.id, user_id=aarav.id)
    await db_session.commit()
    await db_session.refresh(contact)
    assert contact.claimed_by == priya.id

    await service.release_claim(db_session, contact_id=contact.id, user_id=priya.id)
    await db_session.commit()
    await db_session.refresh(contact)
    assert contact.claimed_by is None


async def test_log_send_on_missing_contact_raises_not_found(
    db_session: AsyncSession, world
):
    import uuid

    with pytest.raises(service.NotFound):
        await service.log_send(
            db_session, contact_id=uuid.uuid4(),
            user_id=world["priya"].id, kind="initial",
        )
