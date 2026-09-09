"""
HTTP-level tests for Dyslexic contacts and the drafting claim.

The claim is what stops two volunteers writing the same email in parallel, so
its conflict behaviour and its self-expiry are both asserted here.
"""

from datetime import datetime, timedelta, timezone
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.db.models import DyslexicContact, User
from app.main import app
from conftest import request_as


@pytest.fixture(autouse=True)
def override_db(db_session: AsyncSession):
    async def _get_test_session():
        yield db_session

    app.dependency_overrides[get_session] = _get_test_session
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def no_background_research(monkeypatch):
    from app.routers import dyslexic as router_module

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(router_module, "run_research_task", _noop)


async def client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
async def setup(db_session: AsyncSession):
    priya = User(display_name="Priya", email="priya@bnb.org")
    aarav = User(display_name="Aarav", email="aarav@bnb.org")
    db_session.add_all([priya, aarav])
    await db_session.commit()

    async with await client() as ac:
        created = await request_as(
            ac, priya.id, "POST", "/api/dyslexic/companies",
            json={"name": "Zomato", "website": "zomato.com"},
        )
    return {"priya": priya, "aarav": aarav, "company_id": created.json()["id"]}


async def test_create_contact_lowercases_email_and_advances_stage(setup):
    async with await client() as ac:
        response = await request_as(
            ac, setup["priya"].id, "POST",
            f"/api/dyslexic/companies/{setup['company_id']}/contacts",
            json={"name": "Dev Rel Lead", "email": "DevRel@Zomato.COM", "role": "DevRel"},
        )

        company = await request_as(
            ac, setup["priya"].id, "GET",
            f"/api/dyslexic/companies/{setup['company_id']}",
        )

    assert response.status_code == 201
    assert response.json()["email"] == "devrel@zomato.com"
    assert response.json()["duplicate_warning"] is None
    assert company.json()["stage"] == "contacts_added"


async def test_same_email_twice_at_one_company_is_refused(setup):
    async with await client() as ac:
        path = f"/api/dyslexic/companies/{setup['company_id']}/contacts"
        first = await request_as(
            ac, setup["priya"].id, "POST", path,
            json={"name": "Dev Rel", "email": "devrel@zomato.com"},
        )
        second = await request_as(
            ac, setup["priya"].id, "POST", path,
            json={"name": "Dev Rel Again", "email": "DEVREL@zomato.com"},
        )

    assert first.status_code == 201
    assert second.status_code == 409


async def test_same_person_at_another_company_warns_but_succeeds(setup):
    """People change jobs. Warn, don't block."""
    async with await client() as ac:
        await request_as(
            ac, setup["priya"].id, "POST",
            f"/api/dyslexic/companies/{setup['company_id']}/contacts",
            json={"name": "Dev Rel", "email": "person@example.com"},
        )

        other = await request_as(
            ac, setup["priya"].id, "POST", "/api/dyslexic/companies",
            json={"name": "Swiggy", "website": "swiggy.com"},
        )
        response = await request_as(
            ac, setup["priya"].id, "POST",
            f"/api/dyslexic/companies/{other.json()['id']}/contacts",
            json={"name": "Dev Rel", "email": "person@example.com"},
        )

    assert response.status_code == 201
    assert "Zomato" in response.json()["duplicate_warning"]


async def test_claim_conflict_names_the_holder(setup):
    async with await client() as ac:
        contact = await request_as(
            ac, setup["priya"].id, "POST",
            f"/api/dyslexic/companies/{setup['company_id']}/contacts",
            json={"name": "Dev Rel", "email": "devrel@zomato.com"},
        )
        contact_id = contact.json()["id"]

        mine = await request_as(
            ac, setup["priya"].id, "POST",
            f"/api/dyslexic/contacts/{contact_id}/claim",
        )
        theirs = await request_as(
            ac, setup["aarav"].id, "POST",
            f"/api/dyslexic/contacts/{contact_id}/claim",
        )

    assert mine.status_code == 200
    assert theirs.status_code == 409
    assert theirs.json()["detail"]["claimed_by"] == "Priya"


async def test_claim_can_be_released_and_retaken(setup):
    async with await client() as ac:
        contact = await request_as(
            ac, setup["priya"].id, "POST",
            f"/api/dyslexic/companies/{setup['company_id']}/contacts",
            json={"name": "Dev Rel", "email": "devrel@zomato.com"},
        )
        contact_id = contact.json()["id"]

        await request_as(
            ac, setup["priya"].id, "POST", f"/api/dyslexic/contacts/{contact_id}/claim"
        )
        released = await request_as(
            ac, setup["priya"].id, "DELETE",
            f"/api/dyslexic/contacts/{contact_id}/claim",
        )
        retaken = await request_as(
            ac, setup["aarav"].id, "POST",
            f"/api/dyslexic/contacts/{contact_id}/claim",
        )

    assert released.status_code == 204
    assert retaken.status_code == 200


async def test_expired_claim_frees_the_contact(setup, db_session: AsyncSession):
    """No unlock button, no cleanup job — the window just lapses."""
    async with await client() as ac:
        contact = await request_as(
            ac, setup["priya"].id, "POST",
            f"/api/dyslexic/companies/{setup['company_id']}/contacts",
            json={"name": "Dev Rel", "email": "devrel@zomato.com"},
        )
        contact_id = contact.json()["id"]

        await request_as(
            ac, setup["priya"].id, "POST", f"/api/dyslexic/contacts/{contact_id}/claim"
        )

        stored = await db_session.get(DyslexicContact, uuid.UUID(contact_id))
        stored.claim_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        await db_session.commit()

        response = await request_as(
            ac, setup["aarav"].id, "POST",
            f"/api/dyslexic/contacts/{contact_id}/claim",
        )

    assert response.status_code == 200
    assert response.json()["claimed_by_name"] == "Aarav"


async def test_contacts_cannot_be_deleted(setup):
    async with await client() as ac:
        contact = await request_as(
            ac, setup["priya"].id, "POST",
            f"/api/dyslexic/companies/{setup['company_id']}/contacts",
            json={"name": "Dev Rel", "email": "devrel@zomato.com"},
        )
        response = await request_as(
            ac, setup["priya"].id, "DELETE",
            f"/api/dyslexic/contacts/{contact.json()['id']}",
        )

    assert response.status_code == 405
