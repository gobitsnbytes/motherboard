import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.database import get_session
from app.db.models import User
from conftest import request_as


@pytest.fixture(autouse=True)
def override_db(db_session: AsyncSession):
    async def _get_test_session():
        yield db_session
    app.dependency_overrides[get_session] = _get_test_session
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_user(db_session: AsyncSession, super_admin: User):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "display_name": "Test Router User",
            "email": "router_test@example.com",
            "avatar_url": "https://example.com/avatar.png"
        }
        response = await request_as(ac, super_admin.id, "POST", "/api/users/", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["display_name"] == "Test Router User"
        assert data["email"] == "router_test@example.com"
        assert data["avatar_url"] == "https://example.com/avatar.png"
        assert "id" in data
        assert data["is_active"] is True
        assert data["is_super_admin"] is False

        # Verify in DB directly
        user_uuid = uuid.UUID(data["id"])
        user = await db_session.get(User, user_uuid)
        assert user is not None
        assert user.display_name == "Test Router User"


@pytest.mark.asyncio
async def test_list_users(db_session: AsyncSession, super_admin: User):
    # Seed a couple of users
    u1 = User(display_name="User One", email="one@example.com")
    u2 = User(display_name="User Two", email="two@example.com")
    db_session.add_all([u1, u2])
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await request_as(ac, super_admin.id, "GET", "/api/users/")
        assert response.status_code == 200
        data = response.json()
        # Should return at least our two users (and possibly seeded database users)
        display_names = [u["display_name"] for u in data]
        assert "User One" in display_names
        assert "User Two" in display_names


@pytest.mark.asyncio
async def test_get_user_by_id(db_session: AsyncSession, super_admin: User):
    u = User(display_name="Fetch Me", email="fetch@example.com")
    db_session.add(u)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Happy path
        response = await request_as(ac, super_admin.id, "GET", f"/api/users/{u.id}")
        assert response.status_code == 200
        assert response.json()["display_name"] == "Fetch Me"

        # Nonexistent UUID (404)
        nonexistent = uuid.uuid4()
        response = await request_as(ac, super_admin.id, "GET", f"/api/users/{nonexistent}")
        assert response.status_code == 404
        assert response.json()["detail"] == "User not found."

        # Malformed UUID (422)
        response = await request_as(ac, super_admin.id, "GET", "/api/users/not-a-valid-uuid")
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_user(db_session: AsyncSession, super_admin: User):
    u = User(display_name="Original Name", email="orig@example.com")
    db_session.add(u)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {"display_name": "Updated Name", "email": "updated@example.com"}
        response = await request_as(ac, super_admin.id, "PATCH", f"/api/users/{u.id}", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "Updated Name"
        assert data["email"] == "updated@example.com"

        # Verify DB directly
        await db_session.refresh(u)
        assert u.display_name == "Updated Name"
        assert u.email == "updated@example.com"

        # Patch nonexistent user
        nonexistent = uuid.uuid4()
        response = await request_as(ac, super_admin.id, "PATCH", f"/api/users/{nonexistent}", json=payload)
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_deactivate_user(db_session: AsyncSession, super_admin: User):
    u = User(display_name="Deactivatable", email="deact@example.com")
    db_session.add(u)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await request_as(ac, super_admin.id, "DELETE", f"/api/users/{u.id}")
        assert response.status_code == 204

        # Verify soft deletion in DB (is_active = False)
        await db_session.refresh(u)
        assert u.is_active is False

        # Deactivate nonexistent user
        nonexistent = uuid.uuid4()
        response = await request_as(ac, super_admin.id, "DELETE", f"/api/users/{nonexistent}")
        assert response.status_code == 404
