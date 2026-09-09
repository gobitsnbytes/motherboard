"""
HTTP-level tests for Dyslexic companies.

Access is deliberately open — any logged-in member can use the module — so
these also assert that no permission grant is required, and that destructive
routes do not exist.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.db.models import DyslexicCompany, User
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
    """
    Company creation queues AI research. These tests are about HTTP behaviour,
    so the queue call is stubbed out — the AI itself is covered separately.
    """
    from app.routers import dyslexic as router_module

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(router_module, "run_research_task", _noop)


async def make_volunteer(db: AsyncSession, name: str = "Volunteer") -> User:
    """A plain member — no groups, no grants, no super-admin flag."""
    user = User(display_name=name, email=f"{name.lower()}@bnb.org")
    db.add(user)
    await db.commit()
    return user


async def client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_plain_member_can_create_a_company(db_session: AsyncSession):
    """No dyslexic.* grant exists; an ordinary volunteer must still get through."""
    user = await make_volunteer(db_session)

    async with await client() as ac:
        response = await request_as(
            ac, user.id, "POST", "/api/dyslexic/companies",
            json={"name": "Zomato", "website": "https://www.zomato.com/careers"},
        )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "Zomato"
    assert body["normalized_domain"] == "zomato.com"
    assert body["stage"] == "research"
    assert body["research_status"] == "pending"


async def test_duplicate_domain_returns_409_with_the_existing_company(
    db_session: AsyncSession,
):
    """The second volunteer needs a link to the record, not just a refusal."""
    user = await make_volunteer(db_session)

    async with await client() as ac:
        first = await request_as(
            ac, user.id, "POST", "/api/dyslexic/companies",
            json={"name": "Zomato", "website": "https://zomato.com"},
        )
        assert first.status_code == 201
        existing_id = first.json()["id"]

        second = await request_as(
            ac, user.id, "POST", "/api/dyslexic/companies",
            json={"name": "Zomato India", "website": "http://WWW.Zomato.com/about"},
        )

    assert second.status_code == 409
    detail = second.json()["detail"]
    assert detail["existing_company_id"] == existing_id
    assert detail["existing_company_name"] == "Zomato"


async def test_duplicate_name_without_website_returns_409(db_session: AsyncSession):
    """
    With no website there is no domain to compare, and NULLs do not collide in
    Postgres — so the name is the only thing standing between the team and two
    records for one sponsor.
    """
    user = await make_volunteer(db_session)

    async with await client() as ac:
        first = await request_as(
            ac, user.id, "POST", "/api/dyslexic/companies", json={"name": "Swiggy"}
        )
        assert first.status_code == 201

        second = await request_as(
            ac, user.id, "POST", "/api/dyslexic/companies", json={"name": "  swiggy  "}
        )

    assert second.status_code == 409
    assert second.json()["detail"]["existing_company_id"] == first.json()["id"]


async def test_list_filters_by_stage_and_query(db_session: AsyncSession):
    user = await make_volunteer(db_session)

    async with await client() as ac:
        for name, site in [("Zomato", "zomato.com"), ("Swiggy", "swiggy.com")]:
            await request_as(
                ac, user.id, "POST", "/api/dyslexic/companies",
                json={"name": name, "website": site},
            )

        zomato = (
            await db_session.execute(
                select(DyslexicCompany).where(DyslexicCompany.name == "Zomato")
            )
        ).scalar_one()
        zomato.stage = "sponsored"
        await db_session.commit()

        by_stage = await request_as(
            ac, user.id, "GET", "/api/dyslexic/companies?stage=sponsored"
        )
        by_query = await request_as(ac, user.id, "GET", "/api/dyslexic/companies?q=swig")

    assert [c["name"] for c in by_stage.json()] == ["Zomato"]
    assert [c["name"] for c in by_query.json()] == ["Swiggy"]


async def test_archived_companies_are_hidden_by_default(db_session: AsyncSession):
    user = await make_volunteer(db_session)

    async with await client() as ac:
        created = await request_as(
            ac, user.id, "POST", "/api/dyslexic/companies",
            json={"name": "Zomato", "website": "zomato.com"},
        )
        company_id = created.json()["id"]

        await request_as(
            ac, user.id, "PATCH", f"/api/dyslexic/companies/{company_id}",
            json={"is_archived": True},
        )

        default_list = await request_as(ac, user.id, "GET", "/api/dyslexic/companies")
        with_archived = await request_as(
            ac, user.id, "GET", "/api/dyslexic/companies?archived=true"
        )

    assert default_list.json() == []
    assert len(with_archived.json()) == 1


async def test_companies_cannot_be_deleted(db_session: AsyncSession):
    """
    Open access without a delete route is the trade. One misclick must not
    erase a term of outreach history.
    """
    user = await make_volunteer(db_session)

    async with await client() as ac:
        created = await request_as(
            ac, user.id, "POST", "/api/dyslexic/companies",
            json={"name": "Zomato", "website": "zomato.com"},
        )
        response = await request_as(
            ac, user.id, "DELETE",
            f"/api/dyslexic/companies/{created.json()['id']}",
        )

    assert response.status_code == 405


async def test_company_detail_includes_contacts_and_timeline(db_session: AsyncSession):
    user = await make_volunteer(db_session)

    async with await client() as ac:
        created = await request_as(
            ac, user.id, "POST", "/api/dyslexic/companies",
            json={"name": "Zomato", "website": "zomato.com"},
        )
        company_id = created.json()["id"]

        await request_as(
            ac, user.id, "POST", f"/api/dyslexic/companies/{company_id}/contacts",
            json={"name": "Dev Rel", "email": "devrel@zomato.com"},
        )

        detail = await request_as(
            ac, user.id, "GET", f"/api/dyslexic/companies/{company_id}"
        )

    body = detail.json()
    assert len(body["contacts"]) == 1
    assert body["contacts"][0]["name"] == "Dev Rel"
    kinds = [event["kind"] for event in body["timeline"]]
    assert "company.added" in kinds
    assert "contact.added" in kinds


async def test_unauthenticated_requests_are_rejected():
    """Open to members still means members — not the public internet."""
    async with await client() as ac:
        response = await ac.get("/api/dyslexic/companies")

    assert response.status_code == 401
