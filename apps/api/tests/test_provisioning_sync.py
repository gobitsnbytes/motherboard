import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, Group, Membership, DiscordAccount, DiscordRoleMapping, SyncRun
from app.provisioning.client import DiscordClient
from app.provisioning.sync import run_sync


@pytest.mark.asyncio
async def test_sync_happy_path(db_session: AsyncSession):
    # 1. Create a group
    group = Group(slug="sg_tech_lead", name="Tech Lead", is_system=True)
    db_session.add(group)
    await db_session.commit()

    # 2. Create role mapping
    mapping = DiscordRoleMapping(
        discord_role_id="role_123",
        discord_role_name="Discord Tech Lead",
        group_id=group.id,
        sync_enabled=True,
        priority=0,
    )
    db_session.add(mapping)

    # 3. Create a registered User with a DiscordAccount
    user = User(display_name="Alice", is_active=True)
    db_session.add(user)
    await db_session.commit()

    da = DiscordAccount(
        user_id=user.id,
        discord_id="discord_alice",
        username="alice_on_discord",
    )
    db_session.add(da)
    await db_session.commit()

    # 4. Mock DiscordClient
    mock_client = MagicMock(spec=DiscordClient)
    mock_client.get_guild_members = AsyncMock(
        return_value=[
            {
                "user": {"id": "discord_alice", "username": "alice_on_discord"},
                "roles": ["role_123", "unknown_role"],
            },
            {
                # Unregistered user
                "user": {"id": "discord_bob", "username": "bob_on_discord"},
                "roles": ["role_123"],
            },
        ]
    )

    # Run sync
    sync_run = await run_sync(
        db=db_session,
        discord_client=mock_client,
        guild_id="guild_123",
        trigger="manual",
    )

    assert sync_run.status == "completed"
    assert sync_run.members_synced == 1
    assert sync_run.members_added == 1
    assert sync_run.members_removed == 0
    assert len(sync_run.errors) == 0
    assert sync_run.discord_member_count == 2

    # Verify membership created
    stmt = select(Membership).where(Membership.user_id == user.id)
    res = await db_session.execute(stmt)
    memberships = res.scalars().all()
    assert len(memberships) == 1
    assert memberships[0].group_id == group.id
    assert memberships[0].source == "discord_sync"


@pytest.mark.asyncio
async def test_sync_removes_stale_memberships(db_session: AsyncSession):
    # User currently has membership from discord_sync, but role is removed on Discord
    group = Group(slug="sg_tech_lead", name="Tech Lead", is_system=True)
    db_session.add(group)
    await db_session.commit()

    mapping = DiscordRoleMapping(
        discord_role_id="role_123",
        discord_role_name="Discord Tech Lead",
        group_id=group.id,
        sync_enabled=True,
        priority=0,
    )
    db_session.add(mapping)

    user = User(display_name="Alice", is_active=True)
    db_session.add(user)
    await db_session.commit()

    da = DiscordAccount(
        user_id=user.id,
        discord_id="discord_alice",
        username="alice_on_discord",
    )
    db_session.add(da)

    # Add existing membership from sync
    existing_mem = Membership(
        user_id=user.id,
        group_id=group.id,
        source="discord_sync",
    )
    db_session.add(existing_mem)
    await db_session.commit()

    # Mock client returns user with no roles
    mock_client = MagicMock(spec=DiscordClient)
    mock_client.get_guild_members = AsyncMock(
        return_value=[
            {
                "user": {"id": "discord_alice", "username": "alice_on_discord"},
                "roles": [],  # role removed
            }
        ]
    )

    sync_run = await run_sync(
        db=db_session,
        discord_client=mock_client,
        guild_id="guild_123",
    )

    assert sync_run.status == "completed"
    assert sync_run.members_removed == 1

    # Verify membership deleted
    stmt = select(Membership).where(Membership.user_id == user.id)
    res = await db_session.execute(stmt)
    assert len(res.scalars().all()) == 0


@pytest.mark.asyncio
async def test_sync_preserves_manual_memberships(db_session: AsyncSession):
    # Manual membership should not be deleted even if roles don't match
    group = Group(slug="sg_tech_lead", name="Tech Lead", is_system=True)
    db_session.add(group)
    await db_session.commit()

    mapping = DiscordRoleMapping(
        discord_role_id="role_123",
        discord_role_name="Discord Tech Lead",
        group_id=group.id,
        sync_enabled=True,
        priority=0,
    )
    db_session.add(mapping)

    user = User(display_name="Alice", is_active=True)
    db_session.add(user)
    await db_session.commit()

    da = DiscordAccount(
        user_id=user.id,
        discord_id="discord_alice",
        username="alice_on_discord",
    )
    db_session.add(da)

    # Add existing MANUAL membership
    existing_mem = Membership(
        user_id=user.id,
        group_id=group.id,
        source="manual",  # manual!
    )
    db_session.add(existing_mem)
    await db_session.commit()

    mock_client = MagicMock(spec=DiscordClient)
    mock_client.get_guild_members = AsyncMock(
        return_value=[
            {
                "user": {"id": "discord_alice", "username": "alice_on_discord"},
                "roles": [],  # no mapped roles
            }
        ]
    )

    sync_run = await run_sync(
        db=db_session,
        discord_client=mock_client,
        guild_id="guild_123",
    )

    assert sync_run.status == "completed"
    assert sync_run.members_removed == 0

    # Verify manual membership still exists
    stmt = select(Membership).where(Membership.user_id == user.id)
    res = await db_session.execute(stmt)
    mems = res.scalars().all()
    assert len(mems) == 1
    assert mems[0].source == "manual"
