import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.database import get_session
from app.db.models import User, Group, DiscordRoleMapping, Grant


@pytest.fixture(autouse=True)
def override_db(db_session: AsyncSession):
    async def _get_test_session():
        yield db_session
    app.dependency_overrides[get_session] = _get_test_session
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_me(db_session: AsyncSession):
    # Create a super admin user
    user = User(display_name="Admin User", is_super_admin=True)
    db_session.add(user)
    await db_session.commit()

    # Create a grant for this user
    grant = Grant(
        principal_type="user",
        principal_id=user.id,
        permission_key="iam.grants.read",
        resource_scope="global"
    )
    db_session.add(grant)
    await db_session.commit()

    headers = {"X-User-Id": str(user.id)}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/iam/me", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["principal"]["user_id"] == str(user.id)
        assert data["principal"]["is_super_admin"] is True
        assert len(data["grants"]) == 1
        assert data["grants"][0]["permission_key"] == "iam.grants.read"


@pytest.mark.asyncio
async def test_create_group_auto_slugify(db_session: AsyncSession):
    user = User(display_name="Admin User", is_super_admin=True)
    db_session.add(user)
    await db_session.commit()

    headers = {"X-User-Id": str(user.id)}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create a group without providing a slug
        payload = {"name": "Staff Developers", "description": "Global dev staff"}
        response = await ac.post("/api/iam/groups", json=payload, headers=headers)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Staff Developers"
        assert data["slug"] == "staff-developers"
        assert data["is_system"] is False

        # Attempt to create group with same name (slug conflict)
        response = await ac.post("/api/iam/groups", json=payload, headers=headers)
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upsert_discord_mapping_priority(db_session: AsyncSession):
    user = User(display_name="Admin User", is_super_admin=True)
    db_session.add(user)
    await db_session.commit()

    group = Group(name="Track Tech", slug="sg_track_tech")
    db_session.add(group)
    await db_session.commit()

    headers = {"X-User-Id": str(user.id)}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "discord_role_id": "role_1001",
            "discord_role_name": "Discord Tech",
            "group_id": str(group.id),
            "sync_enabled": True,
            "priority": 42
        }
        # Insert mapping
        response = await ac.put("/api/iam/discord-mappings", json=payload, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["priority"] == 42
        assert data["discord_role_id"] == "role_1001"

        # Update mapping
        payload["priority"] = 99
        response = await ac.put("/api/iam/discord-mappings", json=payload, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["priority"] == 99

        # Verify database record directly
        stmt = select(DiscordRoleMapping).where(DiscordRoleMapping.discord_role_id == "role_1001")
        res = await db_session.execute(stmt)
        record = res.scalar_one()
        assert record.priority == 99
