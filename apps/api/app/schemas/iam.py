import uuid
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, ConfigDict, Field

# Principal

class ResolvedPrincipalResponse(BaseModel):
    user_id: uuid.UUID
    group_ids: List[uuid.UUID]
    is_super_admin: bool

# Permissions

class PermissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    description: Optional[str] = None
    plugin_id: Optional[str] = None
    created_at: datetime

class PermissionCreate(BaseModel):
    key: str
    description: Optional[str] = None
    plugin_id: Optional[str] = None

# Grants

class GrantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    principal_type: str
    principal_id: uuid.UUID
    permission_key: str
    resource_scope: Optional[str] = None
    granted_by: Optional[uuid.UUID] = None
    expires_at: Optional[datetime] = None
    created_at: datetime

class GrantCreate(BaseModel):
    principal_type: str
    principal_id: uuid.UUID
    permission_key: str
    resource_scope: Optional[str] = None
    expires_at: Optional[datetime] = None

# Groups

class GroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    description: Optional[str] = None
    is_system: bool
    created_at: datetime
    updated_at: datetime

class GroupCreate(BaseModel):
    name: str
    slug: Optional[str] = None
    description: Optional[str] = None

# Memberships

class MembershipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    group_id: uuid.UUID
    source: str
    granted_by: Optional[uuid.UUID] = None
    granted_at: datetime
    expires_at: Optional[datetime] = None

class MembershipCreate(BaseModel):
    user_id: uuid.UUID
    expires_at: Optional[datetime] = None

# Discord Roles

class DiscordRole(BaseModel):
    id: str
    name: str
    color: int
    hoist: bool
    position: int
    permissions: str
    managed: bool
    mentionable: bool

class DiscordRoleMappingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    discord_role_id: str
    discord_role_name: str
    group_id: uuid.UUID
    sync_enabled: bool
    priority: int
    created_at: datetime
    updated_at: datetime

class DiscordRoleMappingUpsert(BaseModel):
    discord_role_id: str
    discord_role_name: str
    group_id: uuid.UUID
    sync_enabled: bool = True
    priority: int = 0
