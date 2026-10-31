"""Discord is the source of truth: one member's roles, applied live (sign-in and bot events)."""

import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DiscordAccount, DiscordRoleMapping, Group, Membership, User
from app.provisioning import client as provisioning_client
from app.provisioning.sync import diff_groups, sync_member_roles

SECRET = {"X-Internal-Secret": os.environ.get("API_INTERNAL_SECRET", "")}


async def _world(db: AsyncSession, discord_id: str):
    lead = Group(slug=f"lead_{discord_id}", name="Lead", is_system=False)
    member = Group(slug=f"member_{discord_id}", name="Member", is_system=False)
    user = User(display_name="Alice", is_active=True)
    db.add_all([lead, member, user])
    await db.flush()
    db.add_all(
        [
            DiscordRoleMapping(
                discord_role_id=f"r_lead_{discord_id}",
                discord_role_name="Lead",
                group_id=lead.id,
                sync_enabled=True,
                priority=0,
            ),
            DiscordRoleMapping(
                discord_role_id=f"r_member_{discord_id}",
                discord_role_name="Member",
                group_id=member.id,
                sync_enabled=True,
                priority=0,
            ),
            DiscordAccount(user_id=user.id, discord_id=discord_id, username="alice"),
        ]
    )
    await db.commit()
    return user, lead, member


async def _groups_of(db: AsyncSession, user: User) -> dict:
    rows = (
        await db.scalars(select(Membership).where(Membership.user_id == user.id))
    ).all()
    return {m.group_id: m.source for m in rows}


def test_diff_groups_never_touches_manual_memberships():
    add, remove = diff_groups(
        target={"a"}, existing_all={"a", "m"}, existing_sync=set()
    )
    assert add == set() and remove == set()  # already a member by another source
    add, remove = diff_groups(
        target=set(), existing_all={"a", "m"}, existing_sync={"a"}
    )
    assert remove == {
        "a"
    }  # only the sync-owned one goes; manual "m" is not in existing_sync


async def test_role_gained_and_lost_updates_membership_immediately(
    db_session: AsyncSession,
):
    user, lead, member = await _world(db_session, "live-1")

    result = await sync_member_roles(
        db_session, "live-1", ["r_lead_live-1", "r_member_live-1", "unmapped"]
    )
    assert result == {"known": True, "added": 2, "removed": 0}
    assert await _groups_of(db_session, user) == {
        lead.id: "discord_sync",
        member.id: "discord_sync",
    }

    result = await sync_member_roles(db_session, "live-1", ["r_member_live-1"])
    assert result["removed"] == 1
    assert await _groups_of(db_session, user) == {member.id: "discord_sync"}


async def test_leaving_the_guild_revokes_sync_access_but_keeps_manual_membership(
    db_session: AsyncSession,
):
    user, lead, member = await _world(db_session, "live-2")
    db_session.add(Membership(user_id=user.id, group_id=member.id, source="manual"))
    await db_session.commit()
    await sync_member_roles(db_session, "live-2", ["r_lead_live-2"])

    await sync_member_roles(db_session, "live-2", None)
    assert await _groups_of(db_session, user) == {member.id: "manual"}


async def test_unknown_discord_id_is_a_no_op(db_session: AsyncSession):
    assert await sync_member_roles(db_session, "never-signed-in", ["x"]) == {
        "known": False,
        "added": 0,
        "removed": 0,
    }


async def test_bot_endpoint_requires_the_internal_secret(
    client, db_session: AsyncSession
):
    user, lead, _ = await _world(db_session, "live-3")
    body = {"discord_id": "live-3", "roles": ["r_lead_live-3"]}

    assert (await client.post("/api/sync/member", json=body)).status_code == 401
    assert (
        await client.post(
            "/api/sync/member", json=body, headers={"X-Internal-Secret": "wrong"}
        )
    ).status_code == 401
    assert await _groups_of(db_session, user) == {}

    ok = await client.post("/api/sync/member", json=body, headers=SECRET)
    assert ok.status_code == 200 and ok.json()["added"] == 1
    assert lead.id in await _groups_of(db_session, user)


async def test_sign_in_resolves_roles_and_survives_a_discord_outage(
    client, db_session: AsyncSession, monkeypatch
):
    user, lead, _ = await _world(db_session, "live-4")
    monkeypatch.setattr(
        "app.routers.auth.get_settings",
        lambda: type(
            "S",
            (),
            {
                "api_internal_secret": SECRET["X-Internal-Secret"],
                "discord_guild_id": "g1",
            },
        )(),
    )
    seen = {}

    async def roles_ok(token, guild):
        seen["args"] = (token, guild)
        return ["r_lead_live-4"]

    monkeypatch.setattr("app.routers.auth.fetch_own_guild_roles", roles_ok)
    payload = {"discord_id": "live-4", "username": "alice", "access_token": "tok"}
    response = await client.post("/api/auth/upsert", json=payload, headers=SECRET)
    assert response.status_code == 200
    assert seen["args"] == ("tok", "g1")
    assert lead.id in await _groups_of(db_session, user)

    async def roles_down(token, guild):
        raise provisioning_client.DiscordAPIError(503, "discord is down")

    monkeypatch.setattr("app.routers.auth.fetch_own_guild_roles", roles_down)
    response = await client.post("/api/auth/upsert", json=payload, headers=SECRET)
    assert response.status_code == 200  # sign-in is never blocked by Discord
    assert lead.id in await _groups_of(
        db_session, user
    )  # and access is not wiped by an outage
