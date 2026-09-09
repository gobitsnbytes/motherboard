from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.config import get_settings
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
async def test_volunteer_case_creates_scoped_portal(super_admin):
    get_settings().smtp_host = None
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await request_as(
            client,
            super_admin.id,
            "POST",
            "/api/onboarding/cases",
            json={
                "kind": "volunteer",
                "title": "Asha volunteer onboarding",
                "participant": {
                    "name": "Asha Example",
                    "email": "asha@example.com",
                    "date_of_birth": "2005-04-02",
                },
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()
        portal_url = body["participants"][0]["portal_url"]
        token = portal_url.rsplit("/", 1)[-1]
        portal = await client.get(f"/api/onboarding/public/{token}")
        assert portal.status_code == 200
        assert portal.json()["participant"]["email"] == "asha@example.com"


@pytest.mark.asyncio
async def test_minor_requires_parent_and_underage_is_rejected(super_admin):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        minor = await request_as(
            client,
            super_admin.id,
            "POST",
            "/api/onboarding/cases",
            json={
                "kind": "volunteer",
                "title": "Minor volunteer",
                "participant": {"name": "Minor Example", "email": "minor@example.com", "date_of_birth": "2010-04-02"},
            },
        )
        assert minor.status_code == 422
        underage = await request_as(
            client,
            super_admin.id,
            "POST",
            "/api/onboarding/cases",
            json={
                "kind": "volunteer",
                "title": "Too young",
                "participant": {"name": "Child Example", "email": "child@example.com", "date_of_birth": "2015-04-02"},
            },
        )
        assert underage.status_code == 422
