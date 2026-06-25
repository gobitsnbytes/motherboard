"""
Database seed data for the bnb-motherboard platform.

Seeds the following on first boot:
- System groups (super_admin, staff, fork_lead, contributor, member)
- Core permissions (IAM, provisioning, plugin, audit, fork scopes)
- Discord role → group mappings for the bits&bytes guild
- Known city forks
- Default Discord role → group mappings per AGENTS.md role hierarchy
"""

import uuid
from typing import Any

# ---------------------------------------------------------------------------
# System Group Definitions
# ---------------------------------------------------------------------------

SYSTEM_GROUPS: list[dict[str, Any]] = [
    {
        "slug": "sg_super_admin",
        "name": "Super Admin",
        "description": "Full platform access. Bypasses all permission checks.",
        "is_system": True,
        "color_hex": "#f1c40f",
    },
    {
        "slug": "sg_executive",
        "name": "Executive Leadership",
        "description": "HQ & Executive team. Full access to all forks and data.",
        "is_system": True,
        "color_hex": "#97192c",
    },
    {
        "slug": "sg_department_lead",
        "name": "Department Lead",
        "description": "Global track leadership. Cross-fork read & write.",
        "is_system": True,
        "color_hex": "#fc920d",
    },
    {
        "slug": "sg_hq",
        "name": "HQ",
        "description": "Bits&Bytes Foundation core members.",
        "is_system": True,
        "color_hex": "#f1c40f",
    },
    {
        "slug": "sg_fork_lead",
        "name": "Fork Lead",
        "description": "City fork leaders. Full local access to their fork.",
        "is_system": True,
        "color_hex": "#7289da",
    },
    {
        "slug": "sg_tech_lead",
        "name": "Tech Lead",
        "description": "Local tech track lead. Modify tech activities in their fork.",
        "is_system": True,
        "color_hex": "#1f8b4c",
    },
    {
        "slug": "sg_creative_lead",
        "name": "Creative Lead",
        "description": "Local creative track lead.",
        "is_system": True,
        "color_hex": "#ad1457",
    },
    {
        "slug": "sg_ops_lead",
        "name": "Ops Lead",
        "description": "Local operations track lead.",
        "is_system": True,
        "color_hex": "#11806a",
    },
    {
        "slug": "sg_outreach_lead",
        "name": "Outreach Lead",
        "description": "Local outreach track lead.",
        "is_system": True,
        "color_hex": "#a84300",
    },
    {
        "slug": "sg_contributor",
        "name": "Contributor",
        "description": "Base contributor. Auto-granted to all onboarded members.",
        "is_system": True,
        "color_hex": "#00ff94",
    },
    {
        "slug": "sg_track_tech",
        "name": "Tech Track",
        "description": "Global tech track contributor. Cross-fork view access.",
        "is_system": True,
        "color_hex": "#3498db",
    },
    {
        "slug": "sg_track_creative",
        "name": "Creative Track",
        "description": "Global creative track contributor.",
        "is_system": True,
        "color_hex": "#eb459e",
    },
    {
        "slug": "sg_track_ops",
        "name": "Ops Track",
        "description": "Global ops track contributor.",
        "is_system": True,
        "color_hex": "#eb459e",
    },
    {
        "slug": "sg_track_outreach",
        "name": "Outreach Track",
        "description": "Global outreach track contributor.",
        "is_system": True,
        "color_hex": "#e67e22",
    },
    {
        "slug": "sg_member",
        "name": "Community Member",
        "description": "City community role holder. Public view access only.",
        "is_system": True,
        "color_hex": "#5865f2",
    },
]


# ---------------------------------------------------------------------------
# Core Permission Definitions
# ---------------------------------------------------------------------------

CORE_PERMISSIONS: list[dict[str, Any]] = [
    # --- IAM ---
    {"key": "iam.users.read", "description": "View user profiles and account details."},
    {"key": "iam.users.write", "description": "Create, update, and deactivate users."},
    {"key": "iam.groups.read", "description": "View groups and their members."},
    {"key": "iam.groups.write", "description": "Create, edit, and delete groups."},
    {"key": "iam.memberships.write", "description": "Add or remove users from groups."},
    {"key": "iam.permissions.read", "description": "View the permission registry."},
    {"key": "iam.permissions.write", "description": "Register and manage permissions."},
    {"key": "iam.grants.read", "description": "View permission grants."},
    {"key": "iam.grants.write", "description": "Create, update, and revoke grants."},
    {"key": "iam.delegations.write", "description": "Delegate permissions to other users."},
    {"key": "iam.role_mappings.read", "description": "View Discord role → group mappings."},
    {"key": "iam.role_mappings.write", "description": "Manage Discord role → group mappings."},
    # --- Forks ---
    {"key": "forks.read", "description": "View all city forks and their metadata."},
    {"key": "forks.write", "description": "Create, update, and archive forks."},
    {"key": "forks.members.read", "description": "View fork member lists."},
    {"key": "forks.members.write", "description": "Add, update, and remove fork members."},
    # --- Provisioning ---
    {"key": "provisioning.sync.trigger", "description": "Manually trigger a Discord member sync."},
    {"key": "provisioning.sync.read", "description": "View sync run history and status."},
    # --- Plugins ---
    {"key": "plugins.read", "description": "View the plugin registry."},
    {"key": "plugins.write", "description": "Install, enable, disable, and configure plugins."},
    # --- Audit ---
    {"key": "audit.read", "description": "Read the audit log."},
    {"key": "audit.export", "description": "Export the audit log."},
    # --- Admin ---
    {"key": "admin.settings.read", "description": "View platform-wide settings."},
    {"key": "admin.settings.write", "description": "Change platform-wide settings."},
    # --- Finance ---
    {"key": "finance.accounts.read", "description": "View all virtual accounts and their balances."},
    {"key": "finance.accounts.create", "description": "Create new virtual accounts and assign owners."},
    {"key": "finance.accounts.manage", "description": "Edit, deactivate, and adjust balances on virtual accounts."},
    {"key": "finance.cards.read", "description": "View virtual cards across all accounts."},
    {"key": "finance.cards.create", "description": "Issue virtual cards for an account."},
    {"key": "finance.cards.manage", "description": "Deactivate or edit any virtual card."},
    {"key": "finance.requests.read", "description": "View all money requests."},
    {"key": "finance.requests.create", "description": "Submit a money request from pool or another account."},
    {"key": "finance.requests.approve", "description": "Approve or reject pending money requests."},
    {"key": "finance.admin", "description": "Full finance admin access — supersedes all individual finance permissions."},
    # --- Meetings & Transcription ---
    {"key": "meetings.read", "description": "View scheduled meetings, transcripts, and preferences."},
    {"key": "meetings.write", "description": "Schedule, reschedule, start, stop, and configure meetings."},
]


# ---------------------------------------------------------------------------
# Discord Role → System Group Mappings (from AGENTS.md role hierarchy)
# ---------------------------------------------------------------------------

# Format: (discord_role_id, discord_role_name, group_slug, sync_enabled, priority)
DISCORD_ROLE_MAPPINGS: list[tuple[str, str, str, bool, int]] = [
    # Global Admin roles
    ("1480620981587279993", "admin", "sg_super_admin", True, 0),
    ("1506019032015310949", "Executive Leadership", "sg_executive", True, 0),
    ("1506323726223016149", "Department Leads", "sg_department_lead", True, 0),
    ("1509256369994203146", "hq", "sg_hq", True, 0),
    # Fork track leads (also map to department_lead for cross-fork access)
    ("1509224755595841676", "tech-lead", "sg_tech_lead", True, 1),
    ("1509224757579616276", "creative-lead", "sg_creative_lead", True, 1),
    ("1509224760293195927", "ops-lead", "sg_ops_lead", True, 1),
    ("1509224762906247178", "outreach-lead", "sg_outreach_lead", True, 1),
    # Fork Lead
    ("1490410901147488286", "fork-lead", "sg_fork_lead", True, 2),
    # Base contributor
    ("1506019068132462804", "Contributor", "sg_contributor", True, 3),
    # Global track roles
    ("1509224750663073865", "tech", "sg_track_tech", True, 4),
    ("1490412912420847646", "creative", "sg_track_creative", True, 4),
    ("1490413018830471332", "ops", "sg_track_ops", True, 4),
    ("1509224752747909351", "outreach", "sg_track_outreach", True, 4),
    # Legacy builder (also contributor-level)
    ("1480624226414366924", "Builder", "sg_contributor", True, 5),
]


# ---------------------------------------------------------------------------
# Known City Forks
# ---------------------------------------------------------------------------

CITY_FORKS: list[dict[str, Any]] = [
    {
        "slug": "delhi",
        "city_name": "Delhi",
        "discord_city_role_id": "1490411548752085094",
        "discord_contributor_role_id": None,  # No dedicated contributor-delhi role in mapping
    },
    {
        "slug": "mumbai",
        "city_name": "Mumbai",
        "discord_city_role_id": "1490411614292283552",
        "discord_contributor_role_id": None,
    },
    {
        "slug": "bangalore",
        "city_name": "Bangalore",
        "discord_city_role_id": "1490412532152930315",
        "discord_contributor_role_id": "1508766945091260436",
    },
    {
        "slug": "hyderabad",
        "city_name": "Hyderabad",
        "discord_city_role_id": "1490412746951626752",
        "discord_contributor_role_id": "1508767008660000840",
    },
    {
        "slug": "kolkata",
        "city_name": "Kolkata",
        "discord_city_role_id": "1490413148543385822",
        "discord_contributor_role_id": "1508767029593899160",
    },
    {
        "slug": "noida",
        "city_name": "Noida",
        "discord_city_role_id": "1508052355579641856",
        "discord_contributor_role_id": "1508767019745677394",
    },
    {
        "slug": "jaipur",
        "city_name": "Jaipur",
        "discord_city_role_id": "1508052382229987470",
        "discord_contributor_role_id": "1508767044567306310",
    },
    {
        "slug": "solan",
        "city_name": "Solan",
        "discord_city_role_id": "1508052399338688613",
        "discord_contributor_role_id": "1508767065308135525",
    },
    {
        "slug": "beawar",
        "city_name": "Beawar",
        "discord_city_role_id": "1508052414215749683",
        "discord_contributor_role_id": "1508767089081450587",
    },
    {
        "slug": "chennai",
        "city_name": "Chennai",
        "discord_city_role_id": "1490411705983832325",
        "discord_contributor_role_id": None,
    },
    {
        "slug": "kanpur",
        "city_name": "Kanpur",
        "discord_city_role_id": "1490411774472753198",
        "discord_contributor_role_id": None,
    },
    {
        "slug": "lucknow",
        "city_name": "Lucknow",
        "discord_city_role_id": "1490411988902477824",
        "discord_contributor_role_id": None,
    },
]
