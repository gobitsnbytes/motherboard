import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DiscordAccount, Group, Membership, User
from conftest import request_as


async def test_current_user_profile_reads_and_updates_user(
    db_session: AsyncSession, super_admin: User, client
):
    response = await request_as(client, super_admin.id, "GET", "/api/users/me")
    assert response.status_code == 200
    assert response.json()["id"] == str(super_admin.id)
    assert response.json()["display_name"] == super_admin.display_name

    updated = await request_as(
        client,
        super_admin.id,
        "PATCH",
        "/api/users/me",
        json={"display_name": "Updated profile"},
    )
    assert updated.status_code == 200
    assert updated.json()["display_name"] == "Updated profile"
    assert updated.json()["profile_completed"] is True
    await db_session.refresh(super_admin)
    assert super_admin.display_name == "Updated profile"


async def test_create_user(db_session: AsyncSession, super_admin: User, client):
    payload = {
        "display_name": "Test Router User",
        "email": "router_test@example.com",
        "avatar_url": "https://example.com/avatar.png",
    }
    response = await request_as(
        client, super_admin.id, "POST", "/api/users/", json=payload
    )
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


async def test_list_users(db_session: AsyncSession, super_admin: User, client):
    # Seed a couple of users
    u1 = User(display_name="User One", email="one@example.com")
    u2 = User(display_name="User Two", email="two@example.com")
    db_session.add_all([u1, u2])
    await db_session.commit()

    response = await request_as(client, super_admin.id, "GET", "/api/users/")
    assert response.status_code == 200
    data = response.json()
    # Should return at least our two users (and possibly seeded database users)
    display_names = [u["display_name"] for u in data]
    assert "User One" in display_names
    assert "User Two" in display_names


async def test_list_members_only_returns_active_discord_users_with_synced_roles(
    db_session: AsyncSession, super_admin: User, client
):
    linked = User(display_name="Aero", email="discord@example.com", title="Lead")
    unlinked = User(display_name="Manual Record", email="manual@example.com")
    inactive = User(display_name="Inactive Discord", is_active=False)
    db_session.add_all([linked, unlinked, inactive])
    await db_session.flush()
    leadership = Group(slug="leadership", name="Executive Leadership")
    manual_group = Group(slug="manual", name="Manual Group")
    db_session.add_all([leadership, manual_group])
    await db_session.flush()
    db_session.add_all(
        [
            DiscordAccount(
                user_id=linked.id,
                discord_id="905658967005495356",
                username="a3rodev",
            ),
            DiscordAccount(
                user_id=inactive.id,
                discord_id="905658967005495357",
                username="inactive",
            ),
            Membership(
                user_id=linked.id,
                group_id=leadership.id,
                source="discord_sync",
                expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            ),
            Membership(
                user_id=linked.id,
                group_id=manual_group.id,
                source="manual",
            ),
        ]
    )
    await db_session.commit()

    response = await request_as(client, super_admin.id, "GET", "/api/users/members")

    assert response.status_code == 200
    members = response.json()
    aero = next(
        member
        for member in members
        if member["discord_id"] == "905658967005495356"
    )
    assert aero["display_name"] == "Aero"
    assert aero["email"] == "discord@example.com"
    assert aero["discord_username"] == "a3rodev"
    assert [role["slug"] for role in aero["roles"]] == ["leadership"]
    assert all(member["display_name"] != "Manual Record" for member in members)
    assert all(member["display_name"] != "Inactive Discord" for member in members)


async def test_get_user_by_id(db_session: AsyncSession, super_admin: User, client):
    u = User(display_name="Fetch Me", email="fetch@example.com")
    db_session.add(u)
    await db_session.commit()

    # Happy path
    response = await request_as(client, super_admin.id, "GET", f"/api/users/{u.id}")
    assert response.status_code == 200
    assert response.json()["display_name"] == "Fetch Me"

    # Nonexistent UUID (404)
    nonexistent = uuid.uuid4()
    response = await request_as(
        client, super_admin.id, "GET", f"/api/users/{nonexistent}"
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found."

    # Malformed UUID (422)
    response = await request_as(
        client, super_admin.id, "GET", "/api/users/not-a-valid-uuid"
    )
    assert response.status_code == 422


async def test_patch_user(db_session: AsyncSession, super_admin: User, client):
    u = User(display_name="Original Name", email="orig@example.com")
    db_session.add(u)
    await db_session.commit()

    payload = {"display_name": "Updated Name", "email": "updated@example.com"}
    response = await request_as(
        client, super_admin.id, "PATCH", f"/api/users/{u.id}", json=payload
    )
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
    response = await request_as(
        client, super_admin.id, "PATCH", f"/api/users/{nonexistent}", json=payload
    )
    assert response.status_code == 404


async def test_deactivate_user(db_session: AsyncSession, super_admin: User, client):
    u = User(display_name="Deactivatable", email="deact@example.com")
    db_session.add(u)
    await db_session.commit()

    response = await request_as(client, super_admin.id, "DELETE", f"/api/users/{u.id}")
    assert response.status_code == 204

    # Verify soft deletion in DB (is_active = False)
    await db_session.refresh(u)
    assert u.is_active is False

    # Deactivate nonexistent user
    nonexistent = uuid.uuid4()
    response = await request_as(
        client, super_admin.id, "DELETE", f"/api/users/{nonexistent}"
    )
    assert response.status_code == 404
