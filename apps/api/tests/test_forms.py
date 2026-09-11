from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.main import app
from conftest import request_as


@pytest.fixture(autouse=True)
def override_db(db_session: AsyncSession):
    async def _get_test_session():
        yield db_session

    app.dependency_overrides[get_session] = _get_test_session
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_forms_validate_answers_and_return_labeled_responses(super_admin):
    super_admin_id = super_admin.id
    blocks = [
        {"id": "name", "type": "text", "label": "Your name", "required": True},
        {"id": "track", "type": "select", "label": "Track", "required": True, "options": ["Design", "Code"]},
    ]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await request_as(client, super_admin_id, "POST", "/api/forms", json={"title": "Interest form", "slug": "interest-form", "blocks": blocks, "is_published": True})
        assert created.status_code == 201, created.text
        form_id = created.json()["id"]

        invalid = await client.post("/api/forms/public/interest-form/submissions", json={"answers": {"unknown": "value"}, "accepted_terms": True, "idempotency_key": "invalid-answer-key-001"})
        assert invalid.status_code == 422

        submitted = await client.post("/api/forms/public/interest-form/submissions", json={"answers": {"name": "Asha", "track": "Code"}, "accepted_terms": True, "idempotency_key": "valid-answer-key-0001"})
        assert submitted.status_code == 201, submitted.text

        retried = await client.post("/api/forms/public/interest-form/submissions", json={"answers": {"name": "Asha", "track": "Code"}, "accepted_terms": True, "idempotency_key": "valid-answer-key-0001"})
        assert retried.status_code == 200, retried.text
        assert retried.json() == {"id": submitted.json()["id"], "status": "already_submitted"}

        responses = await request_as(client, super_admin_id, "GET", f"/api/forms/{form_id}/submissions")
        assert responses.status_code == 200, responses.text
        assert len(responses.json()) == 1
        assert responses.json()[0]["answers"] == {"name": "Asha", "track": "Code"}
        assert responses.json()[0]["labels"] == {"name": "Your name", "track": "Track"}
