import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.database import get_session
from app.config import get_settings
from app.db.models import User


@pytest.fixture(autouse=True)
def override_db(db_session: AsyncSession):
    async def _get_test_session():
        yield db_session
    app.dependency_overrides[get_session] = _get_test_session
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_key_auth_header_success(db_session: AsyncSession, super_admin: User):
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
async def test_api_key_auth_bearer_success(db_session: AsyncSession, super_admin: User):
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
async def test_api_key_auth_missing(db_session: AsyncSession):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/api/meetings/"
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Missing internal authentication headers"
