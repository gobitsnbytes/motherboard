import pytest
import uuid
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.database import get_session
from app.db.models import User, SyncRun, Grant


@pytest.fixture(autouse=True)
def override_db(db_session: AsyncSession):
    async def _get_test_session():
        yield db_session
    app.dependency_overrides[get_session] = _get_test_session
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_sync_endpoints_require_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Missing header
        response = await ac.get("/api/sync/runs")
        assert response.status_code == 401
        assert "Missing X-User-Id header" in response.json()["detail"]

        # Invalid UUID
        response = await ac.get("/api/sync/runs", headers={"X-User-Id": "invalid-uuid"})
        assert response.status_code == 400
        assert "Invalid X-User-Id format" in response.json()["detail"]

        # Nonexistent user
        nonexistent = uuid.uuid4()
        response = await ac.get("/api/sync/runs", headers={"X-User-Id": str(nonexistent)})
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_sync_endpoints_permission_check(db_session: AsyncSession):
    # Create a user with no permissions
    user = User(display_name="No Perms User", is_super_admin=False)
    db_session.add(user)
    await db_session.commit()

    headers = {"X-User-Id": str(user.id)}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Read runs
        response = await ac.get("/api/sync/runs", headers=headers)
        assert response.status_code == 403

        # Trigger sync
        response = await ac.post("/api/sync/trigger", headers=headers)
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_sync_runs_list_and_get(db_session: AsyncSession):
    # Create super admin
    user = User(display_name="Super Admin", is_super_admin=True)
    db_session.add(user)
    await db_session.commit()

    # Seed some sync runs
    run1 = SyncRun(trigger="manual", status="completed", members_synced=10)
    run2 = SyncRun(trigger="scheduled", status="failed", errors=["Timeout"])
    db_session.add_all([run1, run2])
    await db_session.commit()

    headers = {"X-User-Id": str(user.id)}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # List runs
        response = await ac.get("/api/sync/runs", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2
        statuses = [r["status"] for r in data]
        assert "completed" in statuses
        assert "failed" in statuses

        # Get run by ID
        response = await ac.get(f"/api/sync/runs/{run1.id}", headers=headers)
        assert response.status_code == 200
        assert response.json()["status"] == "completed"
        assert response.json()["members_synced"] == 10

        # Get nonexistent run (404)
        response = await ac.get(f"/api/sync/runs/{uuid.uuid4()}", headers=headers)
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_trigger_sync_authorized(db_session: AsyncSession):
    # Create a normal user with provisioning.sync.trigger grant
    user = User(display_name="Sync Trigger User", is_super_admin=False)
    db_session.add(user)
    await db_session.commit()

    grant = Grant(
        principal_type="user",
        principal_id=user.id,
        permission_key="provisioning.sync.trigger"
    )
    db_session.add(grant)
    await db_session.commit()

    headers = {"X-User-Id": str(user.id)}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Patch background task execution
        with patch("app.provisioning.sync.run_sync", new_callable=AsyncMock) as mock_run_sync:
            response = await ac.post("/api/sync/trigger", headers=headers)
            assert response.status_code == 202
            data = response.json()
            assert data["status"] == "running"
            assert data["trigger"] == "manual"
            run_id = uuid.UUID(data["id"])

            # Verify in DB directly
            run = await db_session.get(SyncRun, run_id)
            assert run is not None
            assert run.status == "running"
