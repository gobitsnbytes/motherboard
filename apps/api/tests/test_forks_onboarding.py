"""End-to-end tests for the fork onboarding pipeline (checklist, stage actions, member writes)."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Fork, User
from app.main import app
from tests.conftest import request_as


async def _create_fork(db_session: AsyncSession, **meta_overrides) -> Fork:
    meta = {
        "section8_aligned": True,
        "agreement_signed": True,
        "safeguarding_compliant": True,
        "financial_isolation": True,
        "track_leads": {
            "tech": "11111111-1111-1111-1111-111111111111",
            "creative": "22222222-2222-2222-2222-222222222222",
            "ops": "33333333-3333-3333-3333-333333333333",
            "outreach": "44444444-4444-4444-4444-444444444444",
        },
    }
    meta.update(meta_overrides)
    fork = Fork(
        slug=f"testfork-{uuid.uuid4().hex[:8]}",
        city_name="Test City",
        is_active=True,
        metadata_json=meta,
    )
    db_session.add(fork)
    await db_session.commit()
    await db_session.refresh(fork)
    return fork


@pytest.fixture(autouse=True)
def override_db(db_session: AsyncSession):
    from app.database import get_session

    async def _get_test_session():
        yield db_session

    app.dependency_overrides[get_session] = _get_test_session
    yield
    app.dependency_overrides.clear()


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_onboarding_detail_returns_seven_steps(db_session, super_admin):
    fork = await _create_fork(db_session)
    async with _client() as ac:
        resp = await request_as(ac, super_admin.id, "GET", f"/api/forks/{fork.id}/onboarding")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["checklist"]) == 7
    # No explicit stage recorded: derivation caps at compliance_check for
    # fully-flagged forks — approval must be a recorded human decision.
    assert body["stage"] == "compliance_check"
    assert body["next_stage"] == "approved"


@pytest.mark.asyncio
async def test_checklist_step_toggle_persists(db_session, super_admin):
    fork = await _create_fork(db_session)
    async with _client() as ac:
        resp = await request_as(
            ac,
            super_admin.id,
            "PATCH",
            f"/api/forks/{fork.id}/onboarding/checklist/github_invite",
            json={"completed": True},
        )
        assert resp.status_code == 200
        steps = {s["key"]: s for s in resp.json()["checklist"]}
        assert steps["github_invite"]["completed"] is True
        assert steps["github_invite"]["completed_by"] == str(super_admin.id)

        unknown = await request_as(
            ac,
            super_admin.id,
            "PATCH",
            f"/api/forks/{fork.id}/onboarding/checklist/not_a_step",
            json={"completed": True},
        )
    assert unknown.status_code == 400


@pytest.mark.asyncio
async def test_advance_blocked_until_exit_requirements_met(db_session, super_admin):
    """A fork with failing compliance sits at 'submitted' and cannot advance."""
    fork = await _create_fork(
        db_session,
        section8_aligned=False,
        agreement_signed=False,
        safeguarding_compliant=False,
        financial_isolation=False,
        track_leads={},
    )
    async with _client() as ac:
        detail = await request_as(ac, super_admin.id, "GET", f"/api/forks/{fork.id}/onboarding")
        assert detail.json()["stage"] == "submitted"

        resp = await request_as(
            ac, super_admin.id, "POST", f"/api/forks/{fork.id}/onboarding/action",
            json={"action": "advance"},
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_full_approval_journey(db_session, super_admin):
    """Complete all 7 checklist steps then advance to approved."""
    fork = await _create_fork(db_session)
    steps = [
        "github_invite", "leads_discord", "email_setup", "website_deploy",
        "notion_share", "first_pulse", "team_event_plan",
    ]
    async with _client() as ac:
        for step in steps:
            r = await request_as(
                ac, super_admin.id, "PATCH",
                f"/api/forks/{fork.id}/onboarding/checklist/{step}",
                json={"completed": True},
            )
            assert r.status_code == 200

        resp = await request_as(
            ac, super_admin.id, "POST", f"/api/forks/{fork.id}/onboarding/action",
            json={"action": "advance"},
        )
        assert resp.status_code == 200, f"advance failed: {resp.text}"
        assert resp.json()["stage"] == "approved"

        again = await request_as(
            ac, super_admin.id, "POST", f"/api/forks/{fork.id}/onboarding/action",
            json={"action": "advance"},
        )
    assert again.status_code == 400


@pytest.mark.asyncio
async def test_reject_requires_reason_and_archives(db_session, super_admin):
    fork = await _create_fork(db_session)
    async with _client() as ac:
        no_reason = await request_as(
            ac, super_admin.id, "POST", f"/api/forks/{fork.id}/onboarding/action",
            json={"action": "reject"},
        )
        assert no_reason.status_code == 400

        resp = await request_as(
            ac, super_admin.id, "POST", f"/api/forks/{fork.id}/onboarding/action",
            json={"action": "reject", "reason": "No active teen leadership."},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["stage"] == "archived"


@pytest.mark.asyncio
async def test_reactivate_archived_fork(db_session, super_admin):
    fork = await _create_fork(db_session)
    from sqlalchemy import update

    await db_session.execute(
        update(Fork)
        .where(Fork.id == fork.id)
        .values(is_active=False, metadata_json={**(fork.metadata_json or {}), "onboarding_stage": "archived"})
    )
    await db_session.commit()

    async with _client() as ac:
        resp = await request_as(
            ac, super_admin.id, "POST", f"/api/forks/{fork.id}/onboarding/action",
            json={"action": "reactivate"},
        )
    assert resp.status_code == 200, f"reactivate failed: {resp.text}"
    body = resp.json()
    assert body["stage"] != "archived"


@pytest.mark.asyncio
async def test_member_add_duplicate_remove(db_session, super_admin):
    fork = await _create_fork(db_session)
    member_user = User(display_name="Fork Member")
    db_session.add(member_user)
    await db_session.commit()

    async with _client() as ac:
        added = await request_as(
            ac, super_admin.id, "POST", f"/api/forks/{fork.id}/members",
            json={"user_id": str(member_user.id), "track": "tech", "local_role": "track_lead"},
        )
        assert added.status_code == 201

        dup = await request_as(
            ac, super_admin.id, "POST", f"/api/forks/{fork.id}/members",
            json={"user_id": str(member_user.id)},
        )
        assert dup.status_code == 409

        removed = await request_as(
            ac, super_admin.id, "DELETE", f"/api/forks/{fork.id}/members/{added.json()['id']}",
        )
        assert removed.status_code == 200
        assert removed.json()["is_active"] is False

        listing = await request_as(ac, super_admin.id, "GET", f"/api/forks/{fork.id}/members")
        assert listing.json() == []
