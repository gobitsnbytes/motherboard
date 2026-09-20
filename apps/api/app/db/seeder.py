"""
Database seeder wrapper — re-exports seeding logic from app.db.seed.
People are intentionally never seeded. Discord OAuth and role sync are the
only identity and authority source.
"""

from app.db.seed import (
    CHART_OF_ACCOUNTS,
    CORE_PERMISSIONS,
    DEFAULT_GROUP_GRANTS,
    DISCORD_ROLE_MAPPINGS,
    OKF_LEGAL_RULES,
    SYSTEM_GROUPS,
    run_seeds,
    seed_chart_of_accounts,
    seed_core_permissions,
    seed_default_group_grants,
    seed_discord_role_mappings,
    seed_okf_rules,
    seed_system_groups,
)

__all__ = [
    "SYSTEM_GROUPS",
    "CORE_PERMISSIONS",
    "DEFAULT_GROUP_GRANTS",
    "DISCORD_ROLE_MAPPINGS",
    "CHART_OF_ACCOUNTS",
    "OKF_LEGAL_RULES",
    "seed_system_groups",
    "seed_core_permissions",
    "seed_default_group_grants",
    "seed_discord_role_mappings",
    "seed_chart_of_accounts",
    "seed_okf_rules",
    "run_seeds",
]
