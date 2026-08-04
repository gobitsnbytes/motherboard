"""
Volunteer analytics.

The counts are computed from the outreach records themselves rather than stored
counters, so these tests build known fixtures and assert exact numbers — the
point is that nobody ever has to type their own stats in.
"""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.db.models import (
    DyslexicCompany,
    DyslexicContact,
    DyslexicFollowUp,
    DyslexicOutreach,
    User,
)
from app.dyslexic.constants import LEADERBOARD_WEIGHTS
from app.dyslexic.stats import dashboard_stats, leaderboard
from app.main import app
from conftest import request_as


@pytest.fixture(autouse=True)
def override_db(db_session: AsyncSession):
    async def _get_test_session():
        yield db_session

    app.dependency_overrides[get_session] = _get_test_session
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def fixtures(db_session: AsyncSession):
    """
    Priya: 2 companies, 2 contacts, 2 initial sends, 1 follow-up, 1 sponsor.
    Aarav: 1 company, 1 contact, 1 initial send, 1 reply.
    One of Priya's sends is 60 days old, to exercise the 30-day window.
    """
    now = datetime.now(timezone.utc)
    old = now - timedelta(days=60)

    priya = User(display_name="Priya", email="priya@bnb.org")
    aarav = User(display_name="Aarav", email="aarav@bnb.org")
    db_session.add_all([priya, aarav])
    await db_session.flush()

    zomato = DyslexicCompany(
        name="Zomato", normalized_domain="zomato.com",
        added_by=priya.id, stage="sponsored",
    )
    swiggy = DyslexicCompany(
        name="Swiggy", normalized_domain="swiggy.com", added_by=priya.id
    )
    razorpay = DyslexicCompany(
        name="Razorpay", normalized_domain="razorpay.com", added_by=aarav.id
    )
    db_session.add_all([zomato, swiggy, razorpay])
    await db_session.flush()
    # created_at is server-defaulted; force one into the past for the window test.
    zomato.created_at = old
    await db_session.flush()

    c1 = DyslexicContact(company_id=zomato.id, name="A", email="a@zomato.com", added_by=priya.id)
    c2 = DyslexicContact(company_id=swiggy.id, name="B", email="b@swiggy.com", added_by=priya.id)
    c3 = DyslexicContact(company_id=razorpay.id, name="C", email="c@razorpay.com", added_by=aarav.id)
    db_session.add_all([c1, c2, c3])
    await db_session.flush()

    db_session.add_all([
        DyslexicOutreach(
            contact_id=c1.id, company_id=zomato.id, kind="initial",
            sent_by=priya.id, sent_at=old, outcome="sponsored",
        ),
        DyslexicOutreach(
            contact_id=c2.id, company_id=swiggy.id, kind="initial",
            sent_by=priya.id, sent_at=now,
        ),
        DyslexicOutreach(
            contact_id=c2.id, company_id=swiggy.id, kind="follow_up",
            sent_by=priya.id, sent_at=now,
        ),
        DyslexicOutreach(
            contact_id=c3.id, company_id=razorpay.id, kind="initial",
            sent_by=aarav.id, sent_at=now, outcome="replied",
        ),
    ])
    await db_session.flush()

    outreach = (await db_session.execute(
        DyslexicOutreach.__table__.select().where(
            DyslexicOutreach.__table__.c.contact_id == c2.id
        )
    )).first()
    db_session.add(
        DyslexicFollowUp(
            outreach_id=outreach.id, contact_id=c2.id, company_id=swiggy.id,
            assigned_to=priya.id, due_at=now - timedelta(days=1), status="pending",
        )
    )
    await db_session.commit()

    return {"priya": priya, "aarav": aarav}


async def test_dashboard_stats_counts(db_session: AsyncSession, fixtures):
    stats = await dashboard_stats(db_session, fixtures["priya"].id)

    assert stats["companies"] == 3
    assert stats["contacts"] == 3
    assert stats["emails_sent"] == 3
    assert stats["replies"] == 1
    assert stats["sponsors_closed"] == 1
    assert stats["follow_ups_due"] == 1
    assert stats["my_follow_ups_due"] == 1

    # Aarav has no overdue follow-ups of his own, but sees the team total.
    aarav_stats = await dashboard_stats(db_session, fixtures["aarav"].id)
    assert aarav_stats["follow_ups_due"] == 1
    assert aarav_stats["my_follow_ups_due"] == 0


async def test_leaderboard_counts_and_weighting(db_session: AsyncSession, fixtures):
    rows = await leaderboard(db_session, period="all")
    by_name = {row["display_name"]: row for row in rows}

    priya = by_name["Priya"]
    assert priya["companies_added"] == 2
    assert priya["contacts_added"] == 2
    assert priya["emails_sent"] == 2
    assert priya["follow_ups_sent"] == 1
    assert priya["sponsors_closed"] == 1
    assert priya["score"] == (
        2 * LEADERBOARD_WEIGHTS["companies_added"]
        + 2 * LEADERBOARD_WEIGHTS["contacts_added"]
        + 2 * LEADERBOARD_WEIGHTS["emails_sent"]
        + 1 * LEADERBOARD_WEIGHTS["follow_ups_sent"]
        + 1 * LEADERBOARD_WEIGHTS["sponsors_closed"]
    )

    aarav = by_name["Aarav"]
    assert aarav["replies_received"] == 1
    assert aarav["emails_sent"] == 1

    # Closing a sponsor must outrank adding volume.
    assert rows[0]["display_name"] == "Priya"


async def test_leaderboard_30d_window_excludes_older_rows(
    db_session: AsyncSession, fixtures
):
    rows = await leaderboard(db_session, period="30d")
    by_name = {row["display_name"]: row for row in rows}

    # Priya's Zomato company and its sponsored send are 60 days old.
    assert by_name["Priya"]["companies_added"] == 1
    assert by_name["Priya"]["emails_sent"] == 1
    assert by_name["Priya"]["sponsors_closed"] == 0


async def test_leaderboard_does_not_multiply_counts_across_tables(
    db_session: AsyncSession, fixtures
):
    """
    A single wide join across companies, contacts and outreach would multiply
    rows against each other and inflate every number. Priya added exactly two
    companies regardless of how much outreach hangs off them.
    """
    rows = await leaderboard(db_session, period="all")
    priya = next(row for row in rows if row["display_name"] == "Priya")
    assert priya["companies_added"] == 2


async def test_stats_endpoint_is_open_to_any_member(db_session: AsyncSession, fixtures):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await request_as(ac, fixtures["aarav"].id, "GET", "/api/dyslexic/stats")
        board = await request_as(
            ac, fixtures["aarav"].id, "GET", "/api/dyslexic/leaderboard?period=all"
        )
        activity = await request_as(ac, fixtures["aarav"].id, "GET", "/api/dyslexic/activity")

    assert response.status_code == 200
    assert response.json()["companies"] == 3
    assert board.status_code == 200
    assert len(board.json()) == 2
    assert activity.status_code == 200


async def test_leaderboard_is_empty_when_nothing_has_happened(
    db_session: AsyncSession,
):
    assert await leaderboard(db_session, period="all") == []
