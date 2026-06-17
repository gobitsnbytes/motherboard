SYSTEM_GROUPS = {
    "SUPER_ADMIN": "sg_super_admin",
    "STAFF": "sg_staff",
    "FORK_LEAD": "sg_fork_lead",
    "CONTRIBUTOR": "sg_contributor",
    "MEMBER": "sg_member",
}

CORE_PERMISSIONS = [
    {"key": "iam.grants.read",      "description": "View permission grants"},
    {"key": "iam.grants.write",     "description": "Create/revoke permission grants"},
    {"key": "iam.groups.read",      "description": "View groups and memberships"},
    {"key": "iam.groups.write",     "description": "Create/update/delete groups"},
    {"key": "iam.roles.sync",       "description": "Trigger Discord role sync"},
    {"key": "audit.read",           "description": "View audit log"},
    {"key": "plugins.manage",       "description": "Enable/disable plugins"},
]
