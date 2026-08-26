"""
Database seeder wrapper — re-exports seeding logic from app.db.seed.
Operational data (forks, team) is intentionally NOT seeded; it is pulled
live from Notion via app.provisioning.notion_sync.
"""

from app.db.seed import (
    CHART_OF_ACCOUNTS,
    CORE_PERMISSIONS,
    DISCORD_ROLE_MAPPINGS,
    OKF_LEGAL_RULES,
    SYSTEM_GROUPS,
    run_seeds,
    seed_chart_of_accounts,
    seed_core_permissions,
    seed_discord_role_mappings,
    seed_okf_rules,
    seed_system_groups,
)

__all__ = [
    "SYSTEM_GROUPS",
    "CORE_PERMISSIONS",
    "DISCORD_ROLE_MAPPINGS",
    "CHART_OF_ACCOUNTS",
    "OKF_LEGAL_RULES",
    "seed_system_groups",
    "seed_core_permissions",
    "seed_discord_role_mappings",
    "seed_chart_of_accounts",
    "seed_okf_rules",
    "run_seeds",
]
