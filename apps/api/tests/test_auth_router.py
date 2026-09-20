import os
import uuid


from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DiscordAccount, User


async def test_upsert_discord_identity_requires_internal_secret(client):
    response = await client.post(
        "/api/auth/upsert",
        json={"discord_id": "123", "username": "test-user"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid internal secret"


async def test_upsert_discord_identity_creates_and_updates_user(
    db_session: AsyncSession, client
):
    payload = {
        "discord_id": "1234567890",
        "email": "discord@example.com",
        "username": "discorduser",
        "global_name": "Discord User",
        "avatar": "avatarhash",
        "access_token": "oauth-token",
    }
    headers = {"X-Internal-Secret": os.environ["API_INTERNAL_SECRET"]}

    response = await client.post("/api/auth/upsert", json=payload, headers=headers)
    assert response.status_code == 200
    user_id = uuid.UUID(response.json()["user_id"])

    updated_payload = {
        **payload,
        "email": "updated@example.com",
        "global_name": "Updated Name",
        "access_token": "new-oauth-token",
    }
    response = await client.post(
        "/api/auth/upsert", json=updated_payload, headers=headers
    )
    assert response.status_code == 200
    assert uuid.UUID(response.json()["user_id"]) == user_id

    user = await db_session.get(User, user_id)
    assert user is not None
    assert user.display_name == "Updated Name"
    assert user.email == "updated@example.com"
    assert (
        user.avatar_url
        == "https://cdn.discordapp.com/avatars/1234567890/avatarhash.png"
    )

    result = await db_session.execute(
        select(DiscordAccount).where(DiscordAccount.discord_id == "1234567890")
    )
    account = result.scalar_one()
    assert account.user_id == user_id
    assert account.username == "discorduser"
    assert account.global_name == "Updated Name"
    assert account.access_token == "new-oauth-token"


async def test_upsert_does_not_reconcile_unlinked_user_by_email(db_session: AsyncSession, client):
    seeded = User(
        display_name="Yash Singh",
        email="yash@gobitsnbytes.org",
        is_super_admin=True,
        title="Chief Executive Officer (CEO)",
    )
    db_session.add(seeded)
    await db_session.commit()

    payload = {
        "discord_id": "999888777666555444",
        "email": "yash@gobitsnbytes.org",
        "username": "yashclouded",
        "global_name": "Yash Singh",
    }
    headers = {"X-Internal-Secret": os.environ["API_INTERNAL_SECRET"]}

    response = await client.post("/api/auth/upsert", json=payload, headers=headers)

    assert response.status_code == 200
    linked_user_id = uuid.UUID(response.json()["user_id"])
    assert linked_user_id != seeded.id

    result = await db_session.execute(
        select(DiscordAccount).where(DiscordAccount.discord_id == "999888777666555444")
    )
    account = result.scalar_one()
    assert account.user_id == linked_user_id

    # An unlinked profile is never treated as the Discord principal.
    result = await db_session.execute(
        select(User).where(func.lower(User.email) == "yash@gobitsnbytes.org")
    )
    assert len(result.scalars().all()) == 2
