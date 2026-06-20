import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.database import get_session
from app.db.models import Group, User
from app.db.seeder import run_seeds
from conftest import request_as


@pytest.fixture(autouse=True)
def override_db(db_session: AsyncSession):
    async def _get_test_session():
        yield db_session
    app.dependency_overrides[get_session] = _get_test_session
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_groups(db_session: AsyncSession, super_admin: User):
    # Run the seeder to populate system groups
    await run_seeds(db_session)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await request_as(ac, super_admin.id, "GET", "/api/groups/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 5  # Seeded system groups like sg_super_admin should be there
        slugs = [g["slug"] for g in data]
        assert "sg_super_admin" in slugs


@pytest.mark.asyncio
async def test_get_group(db_session: AsyncSession, super_admin: User):
    group = Group(slug="test-group-get", name="Test Get Group")
    db_session.add(group)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Happy path
        response = await request_as(ac, super_admin.id, "GET", f"/api/groups/{group.id}")
        assert response.status_code == 200
        assert response.json()["slug"] == "test-group-get"

        # 404
        response = await request_as(ac, super_admin.id, "GET", f"/api/groups/{uuid.uuid4()}")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_group(db_session: AsyncSession, super_admin: User):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "slug": "custom-slug-123",
            "name": "Custom Name",
            "description": "Custom Description",
            "color_hex": "#ff0000"
        }
        response = await request_as(ac, super_admin.id, "POST", "/api/groups/", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["slug"] == "custom-slug-123"
        assert data["is_system"] is False


@pytest.mark.asyncio
async def test_update_group(db_session: AsyncSession, super_admin: User):
    # Non-system group update
    group = Group(slug="updatable", name="Old Name", is_system=False)
    db_session.add(group)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {"name": "New Name", "description": "New Desc"}
        response = await request_as(ac, super_admin.id, "PATCH", f"/api/groups/{group.id}", json=payload)
        assert response.status_code == 200
        assert response.json()["name"] == "New Name"

        # System group update should fail
        system_group = Group(slug="non-updatable", name="Sys Group", is_system=True)
        db_session.add(system_group)
        await db_session.commit()

        response = await request_as(ac, super_admin.id, "PATCH", f"/api/groups/{system_group.id}", json=payload)
        assert response.status_code == 403
        assert "System groups cannot be modified" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_group(db_session: AsyncSession, super_admin: User):
    # Non-system group delete
    group = Group(slug="deletable", name="Deletable", is_system=False)
    db_session.add(group)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await request_as(ac, super_admin.id, "DELETE", f"/api/groups/{group.id}")
        assert response.status_code == 204

        # System group delete should fail
        system_group = Group(slug="non-deletable", name="Sys Group 2", is_system=True)
        db_session.add(system_group)
        await db_session.commit()

        response = await request_as(ac, super_admin.id, "DELETE", f"/api/groups/{system_group.id}")
        assert response.status_code == 403
        assert "System groups cannot be deleted" in response.json()["detail"]


@pytest.mark.asyncio
async def test_group_memberships(db_session: AsyncSession, super_admin: User):
    group = Group(slug="group-mems", name="Mems Group", is_system=False)
    user = User(display_name="Group User")
    db_session.add_all([group, user])
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Add member
        response = await request_as(ac, super_admin.id, "POST", f"/api/groups/{group.id}/members/{user.id}")
        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] == str(user.id)
        assert data["group_id"] == str(group.id)
        assert data["source"] == "manual"

        # List members
        response = await request_as(ac, super_admin.id, "GET", f"/api/groups/{group.id}/members")
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["user_id"] == str(user.id)

        # Remove member
        response = await request_as(ac, super_admin.id, "DELETE", f"/api/groups/{group.id}/members/{user.id}")
        assert response.status_code == 204

        # Nonexistent membership removal (fails with 404)
        response = await request_as(ac, super_admin.id, "DELETE", f"/api/groups/{group.id}/members/{user.id}")
        assert response.status_code == 404
        assert "Membership not found" in response.json()["detail"]
