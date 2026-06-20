import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.db.models import DiscordAccount, User
from app.main import app


@pytest.fixture(autouse=True)
def override_db(db_session: AsyncSession):
    async def _get_test_session():
        yield db_session

    app.dependency_overrides[get_session] = _get_test_session
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_upsert_discord_identity_requires_internal_secret():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/auth/upsert",
            json={"discord_id": "123", "username": "test-user"},
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid internal secret"


@pytest.mark.asyncio
async def test_upsert_discord_identity_creates_and_updates_user(db_session: AsyncSession):
    payload = {
        "discord_id": "1234567890",
        "email": "discord@example.com",
        "username": "discorduser",
        "global_name": "Discord User",
        "avatar": "avatarhash",
        "access_token": "oauth-token",
    }
    headers = {"X-Internal-Secret": os.environ["API_INTERNAL_SECRET"]}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/api/auth/upsert", json=payload, headers=headers)
        assert response.status_code == 200
        user_id = uuid.UUID(response.json()["user_id"])

        updated_payload = {
            **payload,
            "email": "updated@example.com",
            "global_name": "Updated Name",
            "access_token": "new-oauth-token",
        }
        response = await ac.post("/api/auth/upsert", json=updated_payload, headers=headers)
        assert response.status_code == 200
        assert uuid.UUID(response.json()["user_id"]) == user_id

    user = await db_session.get(User, user_id)
    assert user is not None
    assert user.display_name == "Updated Name"
    assert user.email == "updated@example.com"
    assert user.avatar_url == "https://cdn.discordapp.com/avatars/1234567890/avatarhash.png"

    result = await db_session.execute(
        select(DiscordAccount).where(DiscordAccount.discord_id == "1234567890")
    )
    account = result.scalar_one()
    assert account.user_id == user_id
    assert account.username == "discorduser"
    assert account.global_name == "Updated Name"
    assert account.access_token == "new-oauth-token"
