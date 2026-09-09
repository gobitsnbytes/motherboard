import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.database import get_session
from app.config import get_settings
from app.db.models import Grant, Permission, User


@pytest.fixture(autouse=True)
def override_db(db_session: AsyncSession):
    async def _get_test_session():
        yield db_session
    app.dependency_overrides[get_session] = _get_test_session
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_key_auth_header_success(db_session: AsyncSession, monkeypatch):
    service_user = User(display_name="Meeting Service")
    permission = Permission(key="meetings.read")
    db_session.add_all([service_user, permission])
    await db_session.commit()
    db_session.add(Grant(
        principal_type="user",
        principal_id=service_user.id,
        permission_key=permission.key,
    ))
    await db_session.commit()
    monkeypatch.setenv("API_SERVICE_USER_ID", str(service_user.id))
    get_settings.cache_clear()
    settings = get_settings()
    api_key = settings.api_internal_secret

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Request with X-API-Key header
        response = await ac.get(
            "/api/meetings/",
            headers={"X-API-Key": api_key}
        )
        # Should authenticate successfully as the super admin context and return list of meetings
        assert response.status_code == 200
        assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_api_key_auth_bearer_success(db_session: AsyncSession, monkeypatch):
    service_user = User(display_name="Meeting Service")
    permission = Permission(key="meetings.read")
    db_session.add_all([service_user, permission])
    await db_session.commit()
    db_session.add(Grant(
        principal_type="user",
        principal_id=service_user.id,
        permission_key=permission.key,
    ))
    await db_session.commit()
    monkeypatch.setenv("API_SERVICE_USER_ID", str(service_user.id))
    get_settings.cache_clear()
    settings = get_settings()
    api_key = settings.api_internal_secret

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Request with Authorization Bearer header
        response = await ac.get(
            "/api/meetings/",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_api_key_auth_invalid(db_session: AsyncSession):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/api/meetings/",
            headers={"X-API-Key": "invalid-secret-key-123"}
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid API Key"


@pytest.mark.asyncio
async def test_api_key_auth_requires_explicit_service_identity(db_session: AsyncSession):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/api/meetings/",
            headers={"X-API-Key": get_settings().api_internal_secret},
        )
        assert response.status_code == 503
        assert response.json()["detail"] == "API service identity is not configured"


@pytest.mark.asyncio
async def test_api_key_auth_rejects_super_admin_service_identity(db_session: AsyncSession, super_admin: User, monkeypatch):
    monkeypatch.setenv("API_SERVICE_USER_ID", str(super_admin.id))
    get_settings.cache_clear()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/api/meetings/",
            headers={"X-API-Key": get_settings().api_internal_secret},
        )
        assert response.status_code == 500
        assert response.json()["detail"] == "API service identity cannot be a super-admin"


@pytest.mark.asyncio
async def test_api_key_auth_missing(db_session: AsyncSession):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/api/meetings/"
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Missing internal authentication headers"
