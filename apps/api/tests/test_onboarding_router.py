from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.config import get_settings
from app.main import app
from app.db.models import AuditLog, User
from conftest import request_as


@pytest.fixture(autouse=True)
def override_db(db_session: AsyncSession):
    async def _get_test_session():
        yield db_session

    app.dependency_overrides[get_session] = _get_test_session
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_volunteer_case_creates_scoped_portal(super_admin, db_session):
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
        assert body["current_revision_id"]
        assert all(document["revision_id"] == body["current_revision_id"] for document in body["documents"])
        portal_url = body["participants"][0]["portal_url"]
        token = portal_url.rsplit("/", 1)[-1]
        portal = await client.get(f"/api/onboarding/public/{token}")
        assert portal.status_code == 200
        assert portal.json()["participant"]["email"] == "asha@example.com"
        audit_actions = (await db_session.execute(select(AuditLog.action))).scalars().all()
        assert "onboarding.case_created" in audit_actions


@pytest.mark.asyncio
async def test_assigned_reviewer_is_independent_and_records_the_active_revision(super_admin, db_session):
    get_settings().smtp_host = None
    reviewer = User(display_name="Independent Reviewer", is_super_admin=True)
    db_session.add(reviewer)
    await db_session.commit()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        self_assignment = await request_as(
            client,
            super_admin.id,
            "POST",
            "/api/onboarding/cases",
            json={
                "kind": "volunteer",
                "title": "Invalid reviewer",
                "reviewer_id": str(super_admin.id),
                "participant": {"name": "Asha Example", "email": "asha@example.com", "date_of_birth": "2005-04-02"},
            },
        )
        assert self_assignment.status_code == 422
        created = await request_as(
            client,
            super_admin.id,
            "POST",
            "/api/onboarding/cases",
            json={
                "kind": "volunteer",
                "title": "Independent review",
                "reviewer_id": str(reviewer.id),
                "participant": {"name": "Asha Example", "email": "asha@example.com", "date_of_birth": "2005-04-02"},
            },
        )
        assert created.status_code == 201, created.text
        case_id = created.json()["id"]
        reviewed = await request_as(
            client,
            reviewer.id,
            "POST",
            f"/api/onboarding/cases/{case_id}/review",
            json={"decision": "changes_requested", "note": "Please correct the packet details."},
        )
        assert reviewed.status_code == 200, reviewed.text
        assert reviewed.json()["reviews"][0]["decision"] == "changes_requested"
        blocked = await request_as(
            client,
            super_admin.id,
            "POST",
            f"/api/onboarding/cases/{case_id}/review",
            json={"decision": "changes_requested", "note": "Creator must not review."},
        )
        assert blocked.status_code == 403


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
async def test_staff_can_cancel_onboarding_and_revoke_portal_link(super_admin, db_session):
    get_settings().smtp_host = None
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await request_as(
            client,
            super_admin.id,
            "POST",
            "/api/onboarding/cases",
            json={
                "kind": "volunteer",
                "title": "Cancelled volunteer onboarding",
                "participant": {"name": "Asha Example", "email": "asha@example.com", "date_of_birth": "2005-04-02"},
            },
        )
        assert created.status_code == 201, created.text
        body = created.json()
        token = body["participants"][0]["portal_url"].rsplit("/", 1)[-1]
        cancelled = await request_as(
            client,
            super_admin.id,
            "POST",
            f"/api/onboarding/cases/{body['id']}/cancel",
            json={"reason": "Participant asked to withdraw from onboarding."},
        )
        assert cancelled.status_code == 200, cancelled.text
        assert cancelled.json()["status"] == "revoked"
        assert (await client.get(f"/api/onboarding/public/{token}")).status_code == 404
        from app.db.models import AuditLog
        audit = (await db_session.execute(select(AuditLog).where(AuditLog.action == "onboarding.case_cancelled"))).scalar_one()
        assert audit.target_id == body["id"]


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
        document_id = body["documents"][0]["id"]
        editor = (await client.get(f"/api/onboarding/public/{token}/documents/{document_id}/editor")).json()
        values = {}
        for field in editor["fields"]:
            if field["type"] == "signature":
                continue
            if field["type"] == "checkbox":
                values[field["id"]] = True
            elif field["type"] == "choice":
                values[field["id"]] = field["options"][0]
            elif field["type"] == "email":
                values[field["id"]] = "asha@example.com"
            elif field["type"] == "date":
                values[field["id"]] = "2026-09-19"
            else:
                values[field["id"]] = "Test value"
        saved = await client.patch(
            f"/api/onboarding/public/{token}/documents/{document_id}/draft",
            json={"base_revision": editor["document"]["current_revision"], "values": values},
        )
        assert saved.status_code == 200, saved.text
        submitted = await client.post(
            f"/api/onboarding/public/{token}/documents/{document_id}/submit",
            json={"base_revision": saved.json()["document"]["current_revision"], "confirmed_identity": True},
        )
        assert submitted.status_code == 200, submitted.text
        updated = await request_as(
            client,
            super_admin.id,
            "PATCH",
            f"/api/onboarding/cases/{body['id']}/participants/{body['participants'][0]['id']}/email",
            json={"email": "correct@example.com"},
        )
        assert updated.status_code == 409
