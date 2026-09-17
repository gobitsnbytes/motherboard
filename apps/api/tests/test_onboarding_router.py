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


@pytest.mark.asyncio
async def test_staff_can_correct_untouched_volunteer_email_and_rotates_portal_link(super_admin):
    get_settings().smtp_host = None
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await request_as(
            client,
            super_admin.id,
            "POST",
            "/api/onboarding/cases",
            json={
                "kind": "volunteer",
                "title": "Email correction",
                "participant": {"name": "Asha Example", "email": "wrong@example.com", "date_of_birth": "2005-04-02"},
            },
        )
        body = created.json()
        old_url = body["participants"][0]["portal_url"]
        old_token = old_url.rsplit("/", 1)[-1]
        updated = await request_as(
            client,
            super_admin.id,
            "PATCH",
            f"/api/onboarding/cases/{body['id']}/participants/{body['participants'][0]['id']}/email",
            json={"email": "correct@example.com"},
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["email"] == "correct@example.com"
        old_portal = await client.get(f"/api/onboarding/public/{old_token}")
        assert old_portal.status_code == 404
        new_token = updated.json()["portal_url"].rsplit("/", 1)[-1]
        portal = await client.get(f"/api/onboarding/public/{new_token}")
        assert portal.status_code == 200
        assert portal.json()["participant"]["email"] == "correct@example.com"


@pytest.mark.asyncio
async def test_staff_can_resend_untouched_invite_and_rotates_portal_link(super_admin):
    get_settings().smtp_host = None
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await request_as(
            client,
            super_admin.id,
            "POST",
            "/api/onboarding/cases",
            json={
                "kind": "fork",
                "title": "Fork invite resend",
                "fork_name": "Chennai",
                "participant": {"name": "Asha Example", "email": "asha@example.com", "date_of_birth": "2005-04-02"},
            },
        )
        body = created.json()
        old_token = body["participants"][0]["portal_url"].rsplit("/", 1)[-1]
        resent = await request_as(
            client,
            super_admin.id,
            "POST",
            f"/api/onboarding/cases/{body['id']}/participants/{body['participants'][0]['id']}/resend",
        )
        assert resent.status_code == 200, resent.text
        assert resent.json()["email_sent"] is False
        assert (await client.get(f"/api/onboarding/public/{old_token}")).status_code == 404
        new_token = resent.json()["portal_url"].rsplit("/", 1)[-1]
        assert (await client.get(f"/api/onboarding/public/{new_token}")).status_code == 200


@pytest.mark.asyncio
async def test_staff_cannot_correct_email_after_packet_submission(super_admin):
    get_settings().smtp_host = None
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await request_as(
            client,
            super_admin.id,
            "POST",
            "/api/onboarding/cases",
            json={
                "kind": "volunteer",
                "title": "Started packet",
                "participant": {"name": "Asha Example", "email": "asha@example.com", "date_of_birth": "2005-04-02"},
            },
        )
        body = created.json()
        token = body["participants"][0]["portal_url"].rsplit("/", 1)[-1]
        submitted = await client.post(f"/api/onboarding/public/{token}/submit", json={"answers": {}, "confirmed_identity": True})
        if submitted.status_code == 503:
            pytest.skip("DOCX renderer is unavailable in this test environment")
        assert submitted.status_code == 200, submitted.text
        updated = await request_as(
            client,
            super_admin.id,
            "PATCH",
            f"/api/onboarding/cases/{body['id']}/participants/{body['participants'][0]['id']}/email",
            json={"email": "correct@example.com"},
        )
        assert updated.status_code == 409
