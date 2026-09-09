"""
AI research behaviour, with the model mocked.

The Gemini client is never called here. Every test replaces `_call_model`, the
single seam through which research reaches the API. What matters is that a bad
or missing model response degrades cleanly: research is advisory, and a failure
must never block the outreach workflow.
"""

import contextlib
import json

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_session
from app.db.models import DyslexicCompany, DyslexicEvent, User
from app.dyslexic import research
from app.main import app
from conftest import request_as

GOOD_RESPONSE = {
    "summary": "Zomato is an Indian food delivery platform.",
    "industry": "Food delivery",
    "size": "5000+ employees",
    "headquarters": "Gurugram, India",
    "products": ["Food delivery", "Dining out"],
    "sponsorship_angle": "Actively hires engineering graduates from Indian campuses.",
    "suggested_contact_roles": ["Campus Marketing Lead", "Head of Developer Relations"],
    "recent_news": ["Expanded quick commerce"],
    "confidence": "high",
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
    """Research short-circuits without a key; most tests want one present."""
    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_api_key", "test-key", raising=False)
    return settings


def stub_model(monkeypatch, text: str, sources=None):
    def _fake(prompt: str, model: str, key: str):
        return text, (sources or [])

    monkeypatch.setattr(research, "_call_model", _fake)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

async def test_clean_json_is_parsed(monkeypatch):
    stub_model(monkeypatch, json.dumps(GOOD_RESPONSE))

    result = await research.research_company("Zomato", "https://zomato.com")

    assert result.ok
    assert result.data["industry"] == "Food delivery"
    assert result.data["confidence"] == "high"
    assert result.error is None


async def test_fenced_json_is_parsed(monkeypatch):
    """
    Search grounding and JSON response mode don't combine, so the model returns
    prose-shaped text that often arrives wrapped in a markdown fence.
    """
    stub_model(monkeypatch, f"```json\n{json.dumps(GOOD_RESPONSE)}\n```")

    result = await research.research_company("Zomato", "https://zomato.com")

    assert result.ok
    assert result.data["industry"] == "Food delivery"


async def test_json_with_surrounding_prose_is_parsed(monkeypatch):
    stub_model(
        monkeypatch,
        f"Here is what I found:\n{json.dumps(GOOD_RESPONSE)}\nHope that helps.",
    )

    result = await research.research_company("Zomato", None)

    assert result.ok
    assert result.data["industry"] == "Food delivery"


async def test_unparseable_output_fails_and_keeps_the_raw_text(monkeypatch):
    """A bad response should be debuggable, not silently discarded."""
    stub_model(monkeypatch, "I could not find anything about this company.")

    result = await research.research_company("Nonexistent Co", None)

    assert not result.ok
    assert result.raw == "I could not find anything about this company."
    assert "parse" in result.error.lower()


async def test_empty_response_fails_cleanly(monkeypatch):
    stub_model(monkeypatch, "   ")

    result = await research.research_company("Zomato", None)

    assert not result.ok
    assert "empty" in result.error.lower()


async def test_model_exception_is_caught(monkeypatch):
    def _boom(prompt, model, key):
        raise RuntimeError("upstream 503")

    monkeypatch.setattr(research, "_call_model", _boom)

    result = await research.research_company("Zomato", None)

    assert not result.ok
    assert "503" in result.error


async def test_missing_api_key_is_explained_not_raised(monkeypatch):
    """Without a key the module still works — research just isn't available."""
    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_api_key", None, raising=False)

    result = await research.research_company("Zomato", None)

    assert not result.ok
    assert "GEMINI_API_KEY" in result.error
    assert "still add contacts" in result.error


async def test_sources_come_from_grounding_metadata(monkeypatch):
    """
    Citations are read from the response structure, not the model's prose, so
    the model cannot fabricate one.
    """
    sources = [{"title": "Zomato — About", "url": "https://zomato.com/about"}]
    stub_model(monkeypatch, json.dumps(GOOD_RESPONSE), sources=sources)

    result = await research.research_company("Zomato", "https://zomato.com")

    assert result.data["sources"] == sources


# ---------------------------------------------------------------------------
# Background task
# ---------------------------------------------------------------------------

@contextlib.asynccontextmanager
async def _borrow(session):
    """
    Lend the test session to code that opens its own.

    `run_research_task` runs after the response is sent, so it builds a session
    from the global factory. Yielding the test session instead — without closing
    it — lets the real task run against the test database.
    """
    yield session


def use_test_session(monkeypatch, db_session):
    monkeypatch.setattr(
        research, "_session_factory", lambda: (lambda: _borrow(db_session))
    )


async def test_background_task_stores_a_successful_result(
    db_session: AsyncSession, monkeypatch
):
    user = User(display_name="Priya")
    db_session.add(user)
    await db_session.flush()
    company = DyslexicCompany(
        name="Zomato", normalized_domain="zomato.com", added_by=user.id
    )
    db_session.add(company)
    await db_session.commit()
    company_id = company.id

    stub_model(monkeypatch, json.dumps(GOOD_RESPONSE))
    use_test_session(monkeypatch, db_session)

    await research.run_research_task(company_id)

    stored = await db_session.get(DyslexicCompany, company_id)
    await db_session.refresh(stored)
    assert stored.research_status == "complete"
    assert stored.research_json["industry"] == "Food delivery"
    assert stored.research_model == get_settings().dyslexic_gemini_model
    assert stored.research_generated_at is not None

    events = (
        await db_session.execute(
            select(DyslexicEvent).where(DyslexicEvent.company_id == company_id)
        )
    ).scalars().all()
    assert [event.kind for event in events] == ["research.generated"]


async def test_background_task_records_a_parse_failure(
    db_session: AsyncSession, monkeypatch
):
    user = User(display_name="Priya")
    db_session.add(user)
    await db_session.flush()
    company = DyslexicCompany(
        name="Zomato", normalized_domain="zomato.com", added_by=user.id
    )
    db_session.add(company)
    await db_session.commit()
    company_id = company.id

    stub_model(monkeypatch, "no idea, sorry")
    use_test_session(monkeypatch, db_session)

    await research.run_research_task(company_id)

    stored = await db_session.get(DyslexicCompany, company_id)
    await db_session.refresh(stored)
    assert stored.research_status == "failed"
    assert stored.research_raw == "no idea, sorry"
    assert "parse" in stored.research_error.lower()


async def test_background_task_never_leaves_a_company_running(
    db_session: AsyncSession, monkeypatch
):
    """
    A crash mid-task must not strand the row in `running` — the UI would show a
    spinner forever with no way to retry.
    """
    user = User(display_name="Priya")
    db_session.add(user)
    await db_session.flush()
    company = DyslexicCompany(
        name="Zomato", normalized_domain="zomato.com", added_by=user.id
    )
    db_session.add(company)
    await db_session.commit()
    company_id = company.id

    use_test_session(monkeypatch, db_session)

    async def _explode(name, website):
        raise RuntimeError("something unexpected")

    monkeypatch.setattr(research, "research_company", _explode)

    await research.run_research_task(company_id)

    stored = await db_session.get(DyslexicCompany, company_id)
    await db_session.refresh(stored)
    assert stored.research_status == "failed"
    assert stored.research_error is not None


async def test_failed_research_does_not_block_outreach(
    db_session: AsyncSession, monkeypatch
):
    """
    The whole point of making research advisory: a company whose research failed
    is still fully usable.
    """
    from app.routers import dyslexic as router_module

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(router_module, "run_research_task", _noop)

    user = User(display_name="Priya")
    db_session.add(user)
    await db_session.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        created = await request_as(
            ac, user.id, "POST", "/api/dyslexic/companies",
            json={"name": "Zomato", "website": "zomato.com"},
        )
        company_id = created.json()["id"]

        stored = await db_session.get(DyslexicCompany, __import__("uuid").UUID(company_id))
        stored.research_status = "failed"
        stored.research_error = "Could not parse the model's response as JSON."
        await db_session.commit()

        contact = await request_as(
            ac, user.id, "POST", f"/api/dyslexic/companies/{company_id}/contacts",
            json={"name": "Dev Rel", "email": "devrel@zomato.com"},
        )
        sent = await request_as(
            ac, user.id, "POST",
            f"/api/dyslexic/contacts/{contact.json()['id']}/sent",
            json={"kind": "initial"},
        )

    assert contact.status_code == 201
    assert sent.status_code == 201


async def test_retry_resets_status_to_pending(db_session: AsyncSession, monkeypatch):
    from app.routers import dyslexic as router_module

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(router_module, "run_research_task", _noop)

    user = User(display_name="Priya")
    db_session.add(user)
    await db_session.flush()
    company = DyslexicCompany(
        name="Zomato", normalized_domain="zomato.com", added_by=user.id,
        research_status="failed", research_error="boom",
    )
    db_session.add(company)
    await db_session.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await request_as(
            ac, user.id, "POST", f"/api/dyslexic/companies/{company.id}/research"
        )

    assert response.status_code == 202
    await db_session.refresh(company)
    assert company.research_status == "pending"
    assert company.research_error is None
