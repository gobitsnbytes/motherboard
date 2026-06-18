import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Set
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DiscordAccount, DiscordRoleMapping, Membership, SyncRun
from app.provisioning.client import DiscordClient
from app.provisioning.errors import SyncAbortedError

import uuid

logger = logging.getLogger(__name__)


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
            logger.error("Failed to fetch Discord members: %s", e)
            sync_run.status = "failed"
            sync_run.finished_at = datetime.now(timezone.utc)
            sync_run.errors = [f"Failed to fetch Discord members: {e}"]
            await db.commit()
            return sync_run

        sync_run.discord_member_count = len(discord_members)

        # 3. Fetch active role mappings
        mappings_stmt = select(DiscordRoleMapping).where(DiscordRoleMapping.sync_enabled == True)
        mappings_res = await db.execute(mappings_stmt)
        role_mappings = mappings_res.scalars().all()

        # Build mapping_dict: {discord_role_id: group_id}
        mapping_dict = {m.discord_role_id: m.group_id for m in role_mappings}
        logger.debug("Loaded %d active Discord role mappings", len(mapping_dict))

        # 4. Process Discord members
        # Extract all Discord IDs from the fetched members list to scope database queries
        discord_ids = [
            m["user"]["id"] for m in discord_members 
            if "user" in m and "id" in m["user"]
        ]

        # Fetch registered DiscordAccount records matching the guild members
        accounts_stmt = select(DiscordAccount).where(DiscordAccount.discord_id.in_(discord_ids)) if discord_ids else select(DiscordAccount).where(False)
        accounts_res = await db.execute(accounts_stmt)
        accounts = accounts_res.scalars().all()
        accounts_by_discord_id = {acc.discord_id: acc for acc in accounts}
        registered_user_ids = [acc.user_id for acc in accounts]

        # Fetch memberships created by discord_sync only for registered guild members
        memberships_stmt = select(Membership).where(
            Membership.source == "discord_sync",
            Membership.user_id.in_(registered_user_ids)
        ) if registered_user_ids else select(Membership).where(False)
        memberships_res = await db.execute(memberships_stmt)
        sync_memberships = memberships_res.scalars().all()

        # Group memberships by user_id
        memberships_by_user: Dict[Any, List[Membership]] = {}
        for m in sync_memberships:
            memberships_by_user.setdefault(m.user_id, []).append(m)

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

            # Current memberships of the user created by discord_sync
            user_sync_memberships = memberships_by_user.get(user_id, [])
            current_group_ids = {m.group_id for m in user_sync_memberships}

            # Identify groups to add and remove
            groups_to_add = target_group_ids - current_group_ids
            groups_to_remove = current_group_ids - target_group_ids

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
            logger.critical("Failed to write failed status to database: %s", db_err)

        raise e
