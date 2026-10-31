import logging
from datetime import datetime, timezone
from typing import Any, Dict, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DiscordAccount, DiscordRoleMapping, Membership, SyncRun
from app.observability import capture_background_exception
from app.provisioning.client import DiscordClient

import uuid

logger = logging.getLogger(__name__)


def diff_groups(target: set, existing_all: set, existing_sync: set) -> tuple[set, set]:
    """The one rule for what a member's Discord roles change.

    Add a group only if they are not already in it by any source (a manual membership is never
    duplicated or taken over). Remove only memberships this sync created, so manual ones survive.
    """
    return target - existing_all, existing_sync - target


async def load_role_mapping(db: AsyncSession) -> dict[str, uuid.UUID]:
    """{discord_role_id: group_id} for every enabled mapping."""
    rows = await db.execute(
        select(DiscordRoleMapping.discord_role_id, DiscordRoleMapping.group_id).where(
            DiscordRoleMapping.sync_enabled.is_(True)
        )
    )
    return {role_id: group_id for role_id, group_id in rows.all()}


async def sync_member_roles(
    db: AsyncSession, discord_id: str, role_ids: list[str] | None
) -> dict[str, int | bool]:
    """Apply ONE member's current Discord roles. `role_ids=None` means they left the guild.

    Used by the sign-in bridge and by the bot's live role-change events, so a role change reaches
    Motherboard in seconds instead of waiting for the next full sweep. The full sweep in `run_sync`
    applies the same `diff_groups` rule and stays only as a safety net.
    A person who has never signed in has no account yet: nothing to do, their first sign-in resolves it.
    """
    account = await db.scalar(select(DiscordAccount).where(DiscordAccount.discord_id == discord_id))
    if account is None:
        return {"known": False, "added": 0, "removed": 0}

    mapping = await load_role_mapping(db)
    target = {mapping[r] for r in (role_ids or []) if r in mapping}
    memberships = (await db.scalars(select(Membership).where(Membership.user_id == account.user_id))).all()
    existing_all = {m.group_id for m in memberships}
    existing_sync = {m.group_id for m in memberships if m.source == "discord_sync"}
    to_add, to_remove = diff_groups(target, existing_all, existing_sync)

    for group_id in to_add:
        db.add(Membership(user_id=account.user_id, group_id=group_id, source="discord_sync"))
    for m in memberships:
        if m.source == "discord_sync" and m.group_id in to_remove:
            await db.delete(m)
    account.last_synced_at = datetime.now(timezone.utc)
    await db.commit()
    return {"known": True, "added": len(to_add), "removed": len(to_remove)}


async def run_sync(
    db: AsyncSession,
    discord_client: DiscordClient,
    guild_id: str,
    trigger: str = "scheduled",
    existing_run_id: uuid.UUID | None = None,
) -> SyncRun:
    """Synchronize Discord guild roles → PostgreSQL group memberships."""
    logger.info("Starting Discord sync run (trigger: %s, existing_run_id: %s)", trigger, existing_run_id)

    # 1. Create or load SyncRun record
    if existing_run_id:
        sync_run = await db.get(SyncRun, existing_run_id)
        if not sync_run:
            sync_run = SyncRun(
                id=existing_run_id,
                trigger=trigger,
                status="running",
                started_at=datetime.now(timezone.utc),
                errors=[],
            )
            db.add(sync_run)
            await db.commit()
        else:
            sync_run.status = "running"
            sync_run.started_at = datetime.now(timezone.utc)
            sync_run.errors = []
            await db.commit()
    else:
        sync_run = SyncRun(
            trigger=trigger,
            status="running",
            started_at=datetime.now(timezone.utc),
            errors=[],
        )
        db.add(sync_run)
        await db.commit()  # commit to make the 'running' run visible


    try:
        # 2. Fetch all Discord guild members
        try:
            discord_members = await discord_client.get_guild_members(guild_id)
        except Exception as e:
            logger.warning("Failed to fetch Discord members: %s", e)
            capture_background_exception(e, subsystem="discord_sync", operation="fetch_members")
            sync_run.status = "failed"
            sync_run.finished_at = datetime.now(timezone.utc)
            sync_run.errors = [f"Failed to fetch Discord members: {e}"]
            await db.commit()
            return sync_run

        sync_run.discord_member_count = len(discord_members)

        # 3. Fetch active role mappings
        mapping_dict = await load_role_mapping(db)
        logger.debug("Loaded %d active Discord role mappings", len(mapping_dict))

        # 4. Process Discord members
        # Extract all Discord IDs from the fetched members list to scope database queries
        discord_ids = [
            m["user"]["id"] for m in discord_members 
            if "user" in m and "id" in m["user"]
        ]

        # Fetch registered DiscordAccount records matching the guild members
        accounts_stmt = select(DiscordAccount)
        accounts_res = await db.execute(accounts_stmt)
        accounts = accounts_res.scalars().all()
        accounts_by_discord_id = {acc.discord_id: acc for acc in accounts}
        registered_user_ids = [acc.user_id for acc in accounts]

        # Fetch all existing memberships for registered guild members (to check existing user-group pairs)
        memberships_stmt = select(Membership).where(
            Membership.user_id.in_(registered_user_ids)
        ) if registered_user_ids else select(Membership).where(False)
        memberships_res = await db.execute(memberships_stmt)
        all_memberships = memberships_res.scalars().all()

        # Group memberships by user_id
        all_memberships_by_user: Dict[Any, List[Membership]] = {}
        sync_memberships_by_user: Dict[Any, List[Membership]] = {}
        for m in all_memberships:
            all_memberships_by_user.setdefault(m.user_id, []).append(m)
            if m.source == "discord_sync":
                sync_memberships_by_user.setdefault(m.user_id, []).append(m)

        members_synced = 0
        members_added = 0
        members_removed = 0
        errors_list = []

        now = datetime.now(timezone.utc)

        # Sync each discord member
        for member in discord_members:
            discord_id = member.get("user", {}).get("id")
            if not discord_id:
                continue

            # Skip if user not registered in DB
            acc = accounts_by_discord_id.get(discord_id)
            if not acc:
                continue

            members_synced += 1
            user_id = acc.user_id

            # Roles held by member on Discord
            member_roles = member.get("roles", [])

            # Target groups this user should belong to based on role mappings
            target_group_ids = {
                mapping_dict[role_id]
                for role_id in member_roles
                if role_id in mapping_dict
            }

            # All current memberships of the user (any source) and discord_sync managed memberships
            user_all_memberships = all_memberships_by_user.get(user_id, [])
            user_sync_memberships = sync_memberships_by_user.get(user_id, [])

            all_existing_group_ids = {m.group_id for m in user_all_memberships}
            current_sync_group_ids = {m.group_id for m in user_sync_memberships}

            groups_to_add, groups_to_remove = diff_groups(
                target_group_ids, all_existing_group_ids, current_sync_group_ids
            )

            # ADD missing memberships
            for g_id in groups_to_add:
                new_m = Membership(
                    user_id=user_id,
                    group_id=g_id,
                    source="discord_sync",
                )
                db.add(new_m)
                members_added += 1

            # REMOVE stale memberships
            for m in user_sync_memberships:
                if m.group_id in groups_to_remove:
                    await db.delete(m)
                    members_removed += 1

            # Update account.last_synced_at
            acc.last_synced_at = now

        # A successful complete guild fetch also revokes sync-owned access for leavers.
        present_ids = set(discord_ids)
        for account in accounts:
            if account.discord_id not in present_ids:
                for membership in sync_memberships_by_user.get(account.user_id, []):
                    await db.delete(membership)
                    members_removed += 1
                account.last_synced_at = now

        # Update run stats
        sync_run.status = "completed"
        sync_run.finished_at = datetime.now(timezone.utc)
        sync_run.members_synced = members_synced
        sync_run.members_added = members_added
        sync_run.members_removed = members_removed
        sync_run.errors = errors_list

        await db.commit()
        logger.info(
            "Sync run completed successfully. Synced: %d, Added: %d, Removed: %d",
            members_synced,
            members_added,
            members_removed,
        )
        return sync_run

    except Exception as e:
        logger.exception("Unexpected error during sync run")
        await db.rollback()

        # Try to record the failure in DB
        try:
            sync_run.status = "failed"
            sync_run.finished_at = datetime.now(timezone.utc)
            sync_run.errors = [f"Unexpected error: {e}"]
            await db.commit()
        except Exception as db_err:
            logger.critical(
                "Failed to write failed status to database: %s", db_err, exc_info=True
            )

        raise e
