import json
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app import routers
from app.db.models import Grant, User
from conftest import request_as


class DummyResponse:
    def __init__(self, status_code: int, json_data: object):
        self.status_code = status_code
        self._json_data = json_data
        self.text = json.dumps(json_data)

    def json(self):
        return self._json_data


class DummyAsyncClient:
    def __init__(self, timeout: float | None = None):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str, headers: dict[str, str] | None = None):
        if "discord.com/api/v10/guilds" in url:
            return DummyResponse(
                200,
                [
                    {
                        "id": "role_1234",
                        "name": "Contributor",
                        "color": 0,
                        "hoist": False,
                        "position": 1,
                        "permissions": "0",
                        "managed": False,
                        "mentionable": False,
                    }
                ],
            )
        return DummyResponse(404, {"detail": "not found"})


async def test_list_discord_roles_requires_permission(db_session: AsyncSession, client):
    user = User(display_name="Admin User", is_super_admin=False)
    db_session.add(user)
    await db_session.commit()

    response = await request_as(client, user.id, "GET", "/api/iam/discord-roles")
    assert response.status_code == 403


async def test_list_discord_roles_with_permission(
    db_session: AsyncSession, monkeypatch, client
):
    user = User(display_name="Admin User", is_super_admin=False)
    db_session.add(user)
    await db_session.commit()

    grant = Grant(
        principal_type="user",
        principal_id=user.id,
        permission_key="iam.role_mappings.read",
    )
    db_session.add(grant)
    await db_session.commit()

    monkeypatch.setattr(
        routers.iam, "httpx", type("DummyHttpx", (), {"AsyncClient": DummyAsyncClient})
    )

    response = await request_as(client, user.id, "GET", "/api/iam/discord-roles")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert data[0]["id"] == "role_1234"


async def test_upsert_discord_mapping_requires_permission(
    db_session: AsyncSession, client
):
    user = User(display_name="Admin User", is_super_admin=False)
    db_session.add(user)
    await db_session.commit()

    payload = {
        "discord_role_id": "role_1001",
        "discord_role_name": "Discord Tech",
        "group_id": str(uuid.uuid4()),
        "sync_enabled": True,
        "priority": 1,
    }
    response = await request_as(
        client, user.id, "PUT", "/api/iam/discord-mappings", json=payload
    )
    assert response.status_code == 403
