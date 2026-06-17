"""
Database seeder — idempotently inserts seed data on application startup.

Uses INSERT ... ON CONFLICT DO NOTHING for all seed inserts so this is
safe to run multiple times (e.g., on every deploy or container restart).
"""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.seed_data import (
    CITY_FORKS,
    CORE_PERMISSIONS,
    DISCORD_ROLE_MAPPINGS,
    SYSTEM_GROUPS,
)

logger = logging.getLogger(__name__)


async def seed_system_groups(session: AsyncSession) -> None:
    """Insert system groups — idempotent on slug conflict."""
    for g in SYSTEM_GROUPS:
        await session.execute(
            text(
                """
                INSERT INTO groups (id, slug, name, description, is_system, color_hex)
                VALUES (gen_random_uuid(), :slug, :name, :description, :is_system, :color_hex)
                ON CONFLICT (slug) DO NOTHING
                """
            ),
            {
                "slug": g["slug"],
                "name": g["name"],
                "description": g.get("description"),
                "is_system": g.get("is_system", False),
                "color_hex": g.get("color_hex"),
            },
        )
    logger.info("Seeded %d system groups.", len(SYSTEM_GROUPS))


async def seed_core_permissions(session: AsyncSession) -> None:
    """Insert core permissions — idempotent on key conflict."""
    for p in CORE_PERMISSIONS:
        await session.execute(
            text(
                """
                INSERT INTO permissions (id, key, description, plugin_id)
                VALUES (gen_random_uuid(), :key, :description, NULL)
                ON CONFLICT (key) DO NOTHING
                """
            ),
            {"key": p["key"], "description": p.get("description")},
        )
    logger.info("Seeded %d core permissions.", len(CORE_PERMISSIONS))


async def seed_discord_role_mappings(session: AsyncSession) -> None:
    """Insert Discord role → group mappings — idempotent on discord_role_id conflict."""
    for discord_role_id, discord_role_name, group_slug, sync_enabled, priority in DISCORD_ROLE_MAPPINGS:
        await session.execute(
            text(
                """
                INSERT INTO discord_role_mappings
                    (id, discord_role_id, discord_role_name, group_id, sync_enabled, priority)
                SELECT
                    gen_random_uuid(),
                    :discord_role_id,
                    :discord_role_name,
                    g.id,
                    :sync_enabled,
                    :priority
                FROM groups g
                WHERE g.slug = :group_slug
                ON CONFLICT (discord_role_id) DO NOTHING
                """
            ),
            {
                "discord_role_id": discord_role_id,
                "discord_role_name": discord_role_name,
                "group_slug": group_slug,
                "sync_enabled": sync_enabled,
                "priority": priority,
            },
        )
    logger.info("Seeded %d Discord role mappings.", len(DISCORD_ROLE_MAPPINGS))


async def seed_city_forks(session: AsyncSession) -> None:
    """Insert known city forks — idempotent on slug conflict."""
    for fork in CITY_FORKS:
        await session.execute(
            text(
                """
                INSERT INTO forks
                    (id, slug, city_name, discord_city_role_id, discord_contributor_role_id,
                     is_active, metadata)
                VALUES (
                    gen_random_uuid(),
                    :slug, :city_name,
                    :discord_city_role_id,
                    :discord_contributor_role_id,
                    true,
                    '{}'::jsonb
                )
                ON CONFLICT (slug) DO NOTHING
                """
            ),
            {
                "slug": fork["slug"],
                "city_name": fork["city_name"],
                "discord_city_role_id": fork.get("discord_city_role_id"),
                "discord_contributor_role_id": fork.get("discord_contributor_role_id"),
            },
        )
    logger.info("Seeded %d city forks.", len(CITY_FORKS))


async def run_seeds(session: AsyncSession) -> None:
    """Run all seeds within the provided session transaction."""
    logger.info("Running database seeds…")
    await seed_system_groups(session)
    await seed_core_permissions(session)
    # Role mappings depend on groups existing first
    await seed_discord_role_mappings(session)
    await seed_city_forks(session)
    await session.commit()
    logger.info("Database seeds completed.")
