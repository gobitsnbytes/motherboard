"""
Schema-level guarantees for the Dyslexic tables.

These assert the constraints the database itself enforces, independent of any
application code — the duplicate-outreach guard in particular has to hold even
if two requests race past the service-layer check.
"""

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError

from app.db.models import (
    DyslexicCompany,
    DyslexicContact,
    DyslexicOutreach,
    User,
)
from conftest import TestingSessionLocal


@pytest_asyncio.fixture
async def seeded():
    """A user, a company, and a contact to hang outreach off."""
    async with TestingSessionLocal() as session:
        user = User(display_name="Test Volunteer", email="v@example.com")
        session.add(user)
        await session.flush()

        company = DyslexicCompany(
            name="Zomato",
            website="https://zomato.com",
            normalized_domain="zomato.com",
            added_by=user.id,
        )
        session.add(company)
        await session.flush()

        contact = DyslexicContact(
            company_id=company.id,
            name="Priya Sharma",
            email="priya@zomato.com",
            added_by=user.id,
        )
        session.add(contact)
        await session.commit()
        return {
            "user_id": user.id,
            "company_id": company.id,
            "contact_id": contact.id,
        }


async def test_normalized_domain_is_unique(seeded):
    """Two volunteers cannot add the same company twice."""
    async with TestingSessionLocal() as session:
        session.add(
            DyslexicCompany(
                name="Zomato Duplicate",
                website="https://www.zomato.com/careers",
                normalized_domain="zomato.com",
                added_by=seeded["user_id"],
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_same_email_twice_at_one_company_is_rejected(seeded):
    async with TestingSessionLocal() as session:
        session.add(
            DyslexicContact(
                company_id=seeded["company_id"],
                name="Priya S (dupe)",
                email="priya@zomato.com",
                added_by=seeded["user_id"],
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_contacts_without_email_do_not_collide(seeded):
    """NULL emails are distinct — several unknown-address contacts are fine."""
    async with TestingSessionLocal() as session:
        session.add(
            DyslexicContact(
                company_id=seeded["company_id"],
                name="Unknown One",
                email=None,
                added_by=seeded["user_id"],
            )
        )
        session.add(
            DyslexicContact(
                company_id=seeded["company_id"],
                name="Unknown Two",
                email=None,
                added_by=seeded["user_id"],
            )
        )
        await session.commit()


async def test_partial_index_blocks_a_second_initial_outreach(seeded):
    """The duplicate-outreach guarantee, enforced by the database itself."""
    now = datetime.now(timezone.utc)
    async with TestingSessionLocal() as session:
        session.add(
            DyslexicOutreach(
                contact_id=seeded["contact_id"],
                company_id=seeded["company_id"],
                kind="initial",
                sent_by=seeded["user_id"],
                sent_at=now,
            )
        )
        await session.commit()

    async with TestingSessionLocal() as session:
        session.add(
            DyslexicOutreach(
                contact_id=seeded["contact_id"],
                company_id=seeded["company_id"],
                kind="initial",
                sent_by=seeded["user_id"],
                sent_at=now + timedelta(hours=1),
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_multiple_follow_ups_are_allowed(seeded):
    """A contact can be chased more than once — only `initial` is capped."""
    now = datetime.now(timezone.utc)
    async with TestingSessionLocal() as session:
        for offset in (1, 2):
            session.add(
                DyslexicOutreach(
                    contact_id=seeded["contact_id"],
                    company_id=seeded["company_id"],
                    kind="follow_up",
                    sent_by=seeded["user_id"],
                    sent_at=now + timedelta(days=offset),
                )
            )
        await session.commit()
