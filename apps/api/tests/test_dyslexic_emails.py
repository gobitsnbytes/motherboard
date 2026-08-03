"""
Email drafting, with the model mocked.

Drafting is a convenience, not a dependency: when the model is unavailable the
volunteer must still be able to write the email themselves and log the send.
"""

import json

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_session
from app.db.models import DyslexicCompany, DyslexicContact, User
from app.dyslexic import emails
from app.main import app
from conftest import request_as

GOOD_DRAFT = {
    "subject": "Sponsoring bits&bytes in Bangalore",
    "body": "Hi Priya,\n\nWe run student hackathons across India...\n\nThanks,\nAarav",
}


@pytest.fixture(autouse=True)
def override_db(db_session: AsyncSession):
    async def _get_test_session():
        yield db_session

    app.dependency_overrides[get_session] = _get_test_session
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    monkeypatch.setattr(get_settings(), "gemini_api_key", "test-key", raising=False)


def stub_model(monkeypatch, text: str):
    monkeypatch.setattr(emails, "_call_model", lambda prompt, model, key: text)


def capture_prompt(monkeypatch, sink: dict):
    def _fake(prompt, model, key):
        sink["prompt"] = prompt
        return json.dumps(GOOD_DRAFT)

    monkeypatch.setattr(emails, "_call_model", _fake)


@pytest.fixture
async def setup(db_session: AsyncSession):
    user = User(display_name="Aarav", email="aarav@bnb.org")
    db_session.add(user)
    await db_session.flush()

    company = DyslexicCompany(
        name="Zomato",
        normalized_domain="zomato.com",
        added_by=user.id,
        research_status="complete",
        research_json={
            "summary": "Indian food delivery platform.",
            "industry": "Food delivery",
            "sponsorship_angle": "Hires engineering graduates from Indian campuses.",
            "products": ["Food delivery", "Dining out"],
        },
    )
    db_session.add(company)
    await db_session.flush()

    contact = DyslexicContact(
        company_id=company.id, name="Priya Sharma",
        role="Campus Marketing Lead", email="priya@zomato.com", added_by=user.id,
    )
    db_session.add(contact)
    await db_session.commit()

    return {"user": user, "company": company, "contact": contact}


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

async def test_draft_is_parsed_and_returned(monkeypatch):
    stub_model(monkeypatch, json.dumps(GOOD_DRAFT))

    result = await emails.generate_email(
        company_name="Zomato", research_json={"summary": "Food delivery."},
        contact_name="Priya", contact_role="Campus Lead",
    )

    assert result.ok
    assert result.subject == GOOD_DRAFT["subject"]
    assert result.body.startswith("Hi Priya")


async def test_prompt_carries_research_and_brand_rules(monkeypatch):
    """
    The draft is only as specific as what we hand the model, and the brand rules
    are the difference between "bits&bytes" and "Bits & Bytes" going out to a
    sponsor.
    """
    sink: dict = {}
    capture_prompt(monkeypatch, sink)

    await emails.generate_email(
        company_name="Zomato",
        research_json={
            "summary": "Indian food delivery platform.",
            "sponsorship_angle": "Hires engineering graduates.",
            "products": ["Food delivery"],
        },
        contact_name="Priya", contact_role="Campus Lead",
    )

    prompt = sink["prompt"]
    assert "Indian food delivery platform." in prompt
    assert "Hires engineering graduates." in prompt
    assert "Priya" in prompt
    assert "Campus Lead" in prompt
    assert 'Never write "Bits & Bytes"' in prompt


async def test_missing_research_does_not_invent_details(monkeypatch):
    sink: dict = {}
    capture_prompt(monkeypatch, sink)

    await emails.generate_email(
        company_name="Unknown Co", research_json={},
        contact_name="Someone", contact_role=None,
    )

    assert "No research available" in sink["prompt"]


async def test_follow_up_prompt_includes_the_previous_email(monkeypatch):
    sink: dict = {}
    capture_prompt(monkeypatch, sink)

    await emails.generate_email(
        company_name="Zomato", research_json={}, contact_name="Priya",
        contact_role="Campus Lead", kind="follow_up",
        previous_subject="Sponsoring bits&bytes",
        previous_body="Our original note.", days_ago=5,
    )

    prompt = sink["prompt"]
    assert "Sponsoring bits&bytes" in prompt
    assert "Our original note." in prompt
    assert "sent 5 days ago" in prompt
    assert "shorter than the original" in prompt


async def test_unparseable_draft_fails_cleanly(monkeypatch):
    stub_model(monkeypatch, "Sure! Here's an email for you.")

    result = await emails.generate_email(
        company_name="Zomato", research_json={},
        contact_name="Priya", contact_role=None,
    )

    assert not result.ok
    assert result.raw == "Sure! Here's an email for you."


async def test_draft_missing_a_field_fails(monkeypatch):
    stub_model(monkeypatch, json.dumps({"subject": "Hello"}))

    result = await emails.generate_email(
        company_name="Zomato", research_json={},
        contact_name="Priya", contact_role=None,
    )

    assert not result.ok
    assert "missing a subject or body" in result.error


async def test_missing_api_key_is_explained(monkeypatch):
    monkeypatch.setattr(get_settings(), "gemini_api_key", None, raising=False)

    result = await emails.generate_email(
        company_name="Zomato", research_json={},
        contact_name="Priya", contact_role=None,
    )

    assert not result.ok
    assert "still log it as sent" in result.error


# ---------------------------------------------------------------------------
# Route behaviour
# ---------------------------------------------------------------------------

async def test_generating_claims_the_contact(setup, db_session, monkeypatch):
    """Everyone else should see the draft is underway, not find out at send time."""
    stub_model(monkeypatch, json.dumps(GOOD_DRAFT))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await request_as(
            ac, setup["user"].id, "POST",
            f"/api/dyslexic/contacts/{setup['contact'].id}/generate-email",
            json={"kind": "initial"},
        )

    assert response.status_code == 201
    assert response.json()["subject"] == GOOD_DRAFT["subject"]

    await db_session.refresh(setup["contact"])
    assert setup["contact"].claimed_by == setup["user"].id

    await db_session.refresh(setup["company"])
    assert setup["company"].stage == "email_generated"


async def test_cannot_generate_for_a_contact_someone_else_is_drafting(
    setup, db_session, monkeypatch
):
    stub_model(monkeypatch, json.dumps(GOOD_DRAFT))
    other = User(display_name="Priya", email="priya@bnb.org")
    db_session.add(other)
    await db_session.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        first = await request_as(
            ac, setup["user"].id, "POST",
            f"/api/dyslexic/contacts/{setup['contact'].id}/generate-email",
            json={"kind": "initial"},
        )
        second = await request_as(
            ac, other.id, "POST",
            f"/api/dyslexic/contacts/{setup['contact'].id}/generate-email",
            json={"kind": "initial"},
        )

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["detail"]["claimed_by"] == "Aarav"


async def test_model_failure_returns_503_and_outreach_still_works(
    setup, monkeypatch
):
    """
    Drafting is a convenience. When it breaks the volunteer writes the email
    themselves, and logging the send must still succeed.
    """
    def _boom(prompt, model, key):
        raise RuntimeError("upstream 503")

    monkeypatch.setattr(emails, "_call_model", _boom)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        draft = await request_as(
            ac, setup["user"].id, "POST",
            f"/api/dyslexic/contacts/{setup['contact'].id}/generate-email",
            json={"kind": "initial"},
        )
        sent = await request_as(
            ac, setup["user"].id, "POST",
            f"/api/dyslexic/contacts/{setup['contact'].id}/sent",
            json={"kind": "initial"},
        )

    assert draft.status_code == 503
    assert sent.status_code == 201


async def test_drafts_are_kept_and_listed(setup, monkeypatch):
    stub_model(monkeypatch, json.dumps(GOOD_DRAFT))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        await request_as(
            ac, setup["user"].id, "POST",
            f"/api/dyslexic/contacts/{setup['contact'].id}/generate-email",
            json={"kind": "initial"},
        )
        listed = await request_as(
            ac, setup["user"].id, "GET",
            f"/api/dyslexic/contacts/{setup['contact'].id}/emails",
        )

    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["model"] == get_settings().dyslexic_gemini_model
