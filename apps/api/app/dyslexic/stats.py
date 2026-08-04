"""
Dashboard counters and the volunteer leaderboard.

Everything is computed on read. Stored counters drift from reality the first
time a transaction rolls back or a record is corrected, and at this scale —
dozens of volunteers, hundreds of companies — the aggregates are instant.
Materialise later, with evidence, if that stops being true.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    DyslexicCompany,
    DyslexicContact,
    DyslexicFollowUp,
    DyslexicOutreach,
    User,
)

from .constants import LEADERBOARD_WEIGHTS


def _period_cutoff(period: str) -> datetime | None:
    """`30d` windows the leaderboard; anything else means all time."""
    if period == "30d":
        return datetime.now(timezone.utc) - timedelta(days=30)
    return None


async def dashboard_stats(db: AsyncSession, user_id: uuid.UUID) -> dict[str, int]:
    """The seven tiles at the top of the Dyslexic dashboard."""
    now = datetime.now(timezone.utc)

    async def scalar(stmt: Select) -> int:
        return (await db.execute(stmt)).scalar_one() or 0

    companies = await scalar(
        select(func.count())
        .select_from(DyslexicCompany)
        .where(DyslexicCompany.is_archived.is_(False))
    )
    contacts = await scalar(
        select(func.count())
        .select_from(DyslexicContact)
        .where(DyslexicContact.is_archived.is_(False))
    )
    emails_sent = await scalar(
        select(func.count())
        .select_from(DyslexicOutreach)
        .where(DyslexicOutreach.kind == "initial")
    )
    replies = await scalar(
        select(func.count())
        .select_from(DyslexicOutreach)
        .where(DyslexicOutreach.outcome == "replied")
    )
    follow_ups_due = await scalar(
        select(func.count())
        .select_from(DyslexicFollowUp)
        .where(DyslexicFollowUp.status == "pending", DyslexicFollowUp.due_at <= now)
    )
    my_follow_ups_due = await scalar(
        select(func.count())
        .select_from(DyslexicFollowUp)
        .where(
            DyslexicFollowUp.status == "pending",
            DyslexicFollowUp.due_at <= now,
            DyslexicFollowUp.assigned_to == user_id,
        )
    )
    sponsors_closed = await scalar(
        select(func.count())
        .select_from(DyslexicCompany)
        .where(DyslexicCompany.stage == "sponsored")
    )

    return {
        "companies": companies,
        "contacts": contacts,
        "emails_sent": emails_sent,
        "replies": replies,
        "follow_ups_due": follow_ups_due,
        "my_follow_ups_due": my_follow_ups_due,
        "sponsors_closed": sponsors_closed,
    }


async def leaderboard(db: AsyncSession, period: str = "all") -> list[dict]:
    """
    Per-volunteer contribution counts, ranked.

    Five grouped queries — one per source table — merged in Python rather than
    one wide join. Joining outreach, companies and contacts in a single query
    multiplies rows against each other and silently inflates every count.
    """
    cutoff = _period_cutoff(period)
    totals: dict[uuid.UUID, dict[str, int]] = {}

    def bucket(user_id: uuid.UUID) -> dict[str, int]:
        return totals.setdefault(
            user_id, {key: 0 for key in LEADERBOARD_WEIGHTS}
        )

    companies_stmt = (
        select(DyslexicCompany.added_by, func.count())
        .where(DyslexicCompany.added_by.is_not(None))
        .group_by(DyslexicCompany.added_by)
    )
    if cutoff is not None:
        companies_stmt = companies_stmt.where(DyslexicCompany.created_at >= cutoff)
    for user_id, count in await db.execute(companies_stmt):
        bucket(user_id)["companies_added"] = count

    contacts_stmt = (
        select(DyslexicContact.added_by, func.count())
        .where(DyslexicContact.added_by.is_not(None))
        .group_by(DyslexicContact.added_by)
    )
    if cutoff is not None:
        contacts_stmt = contacts_stmt.where(DyslexicContact.created_at >= cutoff)
    for user_id, count in await db.execute(contacts_stmt):
        bucket(user_id)["contacts_added"] = count

    sends_stmt = (
        select(DyslexicOutreach.sent_by, DyslexicOutreach.kind, func.count())
        .where(DyslexicOutreach.sent_by.is_not(None))
        .group_by(DyslexicOutreach.sent_by, DyslexicOutreach.kind)
    )
    if cutoff is not None:
        sends_stmt = sends_stmt.where(DyslexicOutreach.sent_at >= cutoff)
    for user_id, kind, count in await db.execute(sends_stmt):
        key = "emails_sent" if kind == "initial" else "follow_ups_sent"
        bucket(user_id)[key] = count

    # Outcomes are credited to whoever sent the email, not whoever typed in the
    # result — the send is the contribution being measured.
    outcomes_stmt = (
        select(DyslexicOutreach.sent_by, DyslexicOutreach.outcome, func.count())
        .where(
            DyslexicOutreach.sent_by.is_not(None),
            DyslexicOutreach.outcome.in_(
                ["replied", "meeting_scheduled", "sponsored"]
            ),
        )
        .group_by(DyslexicOutreach.sent_by, DyslexicOutreach.outcome)
    )
    if cutoff is not None:
        outcomes_stmt = outcomes_stmt.where(DyslexicOutreach.sent_at >= cutoff)
    outcome_keys = {
        "replied": "replies_received",
        "meeting_scheduled": "meetings_scheduled",
        "sponsored": "sponsors_closed",
    }
    for user_id, outcome, count in await db.execute(outcomes_stmt):
        bucket(user_id)[outcome_keys[outcome]] = count

    if not totals:
        return []

    users = await db.execute(
        select(User.id, User.display_name, User.avatar_url).where(
            User.id.in_(totals.keys())
        )
    )
    profiles = {row.id: row for row in users}

    rows = []
    for user_id, counts in totals.items():
        profile = profiles.get(user_id)
        if profile is None:
            continue
        rows.append(
            {
                "user_id": user_id,
                "display_name": profile.display_name,
                "avatar_url": profile.avatar_url,
                **counts,
                "score": sum(
                    counts[key] * weight for key, weight in LEADERBOARD_WEIGHTS.items()
                ),
            }
        )

    rows.sort(key=lambda row: (-row["score"], row["display_name"]))
    return rows
