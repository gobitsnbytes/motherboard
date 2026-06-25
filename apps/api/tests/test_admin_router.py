import pytest
import uuid
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.database import get_session
from app.db.models import User, SyncRun, Grant, Group, Permission, DiscordRoleMapping
from conftest import request_as


@pytest.fixture(autouse=True)
def override_db(db_session: AsyncSession):
    async def _get_test_session():
        yield db_session
    app.dependency_overrides[get_session] = _get_test_session
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_endpoints_permission_check(db_session: AsyncSession):
    # Create regular user without admin permissions
    user = User(display_name="Regular User", is_super_admin=False)
    db_session.add(user)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Reset cache
        response = await request_as(ac, user.id, "POST", "/api/admin/reset-cache")
        assert response.status_code == 403

        # Rebuild permissions
        response = await request_as(ac, user.id, "POST", "/api/admin/rebuild-permissions")
        assert response.status_code == 403

        # Clear sync state
        response = await request_as(ac, user.id, "POST", "/api/admin/clear-sync-state")
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_reset_cache_no_redis(db_session: AsyncSession):
    user = User(display_name="Super Admin", is_super_admin=True)
    db_session.add(user)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # With redis not configured/connected, should return 400 or 500 depending on mock
        with patch("app.events.event_bus.redis", None):
            response = await request_as(ac, user.id, "POST", "/api/admin/reset-cache")
            assert response.status_code == 400
            assert "Redis cache is not configured" in response.json()["detail"]


@pytest.mark.asyncio
async def test_admin_reset_cache_success(db_session: AsyncSession):
    user = User(display_name="Super Admin", is_super_admin=True)
    db_session.add(user)
    await db_session.commit()

    mock_redis = AsyncMock()
    mock_redis.flushdb = AsyncMock(return_value="OK")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch("app.events.event_bus.redis", mock_redis):
            response = await request_as(ac, user.id, "POST", "/api/admin/reset-cache")
            assert response.status_code == 200
            assert response.json()["status"] == "ok"
            mock_redis.flushdb.assert_called_once()


@pytest.mark.asyncio
async def test_admin_clear_sync_state(db_session: AsyncSession):
    user = User(display_name="Super Admin", is_super_admin=True)
    db_session.add(user)
    
    # Add some mock sync runs
    run1 = SyncRun(trigger="manual", status="completed")
    run2 = SyncRun(trigger="scheduled", status="failed")
    db_session.add_all([run1, run2])
    await db_session.commit()

    # Check initially there are 2 runs
    runs_init = await db_session.scalars(select(SyncRun))
    assert len(runs_init.all()) == 2

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await request_as(ac, user.id, "POST", "/api/admin/clear-sync-state")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    # Verify they were deleted in the DB
    runs_after = await db_session.scalars(select(SyncRun))
    assert len(runs_after.all()) == 0


@pytest.mark.asyncio
async def test_admin_rebuild_permissions(db_session: AsyncSession):
    user = User(display_name="Super Admin", is_super_admin=True)
    db_session.add(user)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch("app.routers.admin.run_seeds", AsyncMock()) as mock_run_seeds:
            response = await request_as(ac, user.id, "POST", "/api/admin/rebuild-permissions")
            assert response.status_code == 200
            assert response.json()["status"] == "ok"
            mock_run_seeds.assert_called_once()
