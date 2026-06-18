"""
SQLAlchemy 2.0 declarative ORM models for the bnb-motherboard platform.

Table hierarchy:
    users                → core identity record (1-to-1 with discord_accounts)
    discord_accounts     → linked Discord OAuth identity
    groups               → internal permission groups (system + admin-created)
    memberships          → user ↔ group membership (with source & expiry tracking)
    discord_role_mappings → Discord role ID ↔ internal Group mapping
    permissions          → permission key registry (core + plugin-scoped)
    grants               → permission grant to a user or group (with optional scope)
    delegations          → temporary permission delegation between users
    plugin_registry      → installed plugin catalogue
    audit_log            → immutable event log for all significant actions
    forks                → city fork entities (e.g., "delhi", "bangalore")
    fork_members         → user ↔ fork membership, with track assignment
    sync_runs            → Discord provisioning sync history
"""

import base64
import hashlib
import uuid
from datetime import datetime
from typing import Any

from cryptography.fernet import Fernet
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.config import get_settings


class EncryptedString(TypeDecorator):
    """Symmetrically encrypted string column for sensitive credentials at rest."""
    impl = Text
    cache_ok = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._fernet = None

    @property
    def fernet(self) -> Fernet:
        if self._fernet is None:
            secret = get_settings().session_secret
            key_hash = hashlib.sha256(secret.encode()).digest()
            fernet_key = base64.urlsafe_b64encode(key_hash)
            self._fernet = Fernet(fernet_key)
        return self._fernet

    def process_bind_param(self, value: str | None, dialect) -> str | None:
        if value is None:
            return None
        return self.fernet.encrypt(value.encode()).decode()

    def process_result_value(self, value: str | None, dialect) -> str | None:
        if value is None:
            return None
        try:
            return self.fernet.decrypt(value.encode()).decode()
        except Exception:
            return value


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


# ---------------------------------------------------------------------------
# Users & Identity
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_super_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    discord_account: Mapped["DiscordAccount | None"] = relationship(
        "DiscordAccount", back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    memberships: Mapped[list["Membership"]] = relationship(
        "Membership",
        back_populates="user",
        foreign_keys="Membership.user_id",
        cascade="all, delete-orphan",
    )
    fork_memberships: Mapped[list["ForkMember"]] = relationship(
        "ForkMember", back_populates="user", cascade="all, delete-orphan"
    )
    granted_memberships: Mapped[list["Membership"]] = relationship(
        "Membership",
        foreign_keys="Membership.granted_by",
        back_populates="grantor",
    )
    audit_events: Mapped[list["AuditLog"]] = relationship(
        "AuditLog", back_populates="actor", foreign_keys="AuditLog.actor_id"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} display_name={self.display_name!r}>"


class DiscordAccount(Base):
    """Linked Discord OAuth identity for a platform user."""

    __tablename__ = "discord_accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    # Discord's numeric snowflake ID stored as string (safe for 64-bit)
    discord_id: Mapped[str] = mapped_column(
        String(25), unique=True, nullable=False, index=True
    )
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    # Discriminator (#1234) — null for new-style usernames
    discriminator: Mapped[str | None] = mapped_column(String(4), nullable=True)
    global_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    avatar_hash: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Encrypted OAuth tokens (store encrypted-at-rest in production)
    access_token: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="discord_account")

    def __repr__(self) -> str:
        return f"<DiscordAccount discord_id={self.discord_id!r}>"


# ---------------------------------------------------------------------------
# Groups & Memberships
# ---------------------------------------------------------------------------

class Group(Base):
    """Internal permission group — can be system-defined or admin-created."""

    __tablename__ = "groups"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # system groups cannot be deleted via the admin UI
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # optional colour for the dashboard badge
    color_hex: Mapped[str | None] = mapped_column(String(7), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    memberships: Mapped[list["Membership"]] = relationship(
        "Membership", back_populates="group", cascade="all, delete-orphan"
    )
    role_mappings: Mapped[list["DiscordRoleMapping"]] = relationship(
        "DiscordRoleMapping", back_populates="group", cascade="all, delete-orphan"
    )
    grants: Mapped[list["Grant"]] = relationship(
        "Grant",
        primaryjoin="and_(Grant.principal_type=='group', foreign(Grant.principal_id)==Group.id)",
        viewonly=True,
    )

    def __repr__(self) -> str:
        return f"<Group slug={self.slug!r}>"


class Membership(Base):
    """User ↔ Group membership record."""

    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "group_id", name="uq_membership_user_group"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # How was this membership created?
    source: Mapped[str] = mapped_column(
        String(50), default="manual", nullable=False
    )  # 'discord_sync' | 'manual' | 'provisioning'
    granted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship(
        "User", back_populates="memberships", foreign_keys=[user_id]
    )
    group: Mapped["Group"] = relationship("Group", back_populates="memberships")
    grantor: Mapped["User | None"] = relationship(
        "User", back_populates="granted_memberships", foreign_keys=[granted_by]
    )

    def __repr__(self) -> str:
        return f"<Membership user={self.user_id} group={self.group_id}>"


# ---------------------------------------------------------------------------
# Discord Role → Group Mapping
# ---------------------------------------------------------------------------

class DiscordRoleMapping(Base):
    """Maps a Discord guild role ID to an internal Group for provisioning sync."""

    __tablename__ = "discord_role_mappings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    discord_role_id: Mapped[str] = mapped_column(
        String(25), unique=True, nullable=False, index=True
    )
    discord_role_name: Mapped[str] = mapped_column(String(100), nullable=False)
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sync_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Priority — lower number = higher precedence when multiple roles map to same group
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    group: Mapped["Group"] = relationship("Group", back_populates="role_mappings")

    def __repr__(self) -> str:
        return f"<DiscordRoleMapping discord_role_id={self.discord_role_id!r} → group={self.group_id}>"


# ---------------------------------------------------------------------------
# Permissions & Grants
# ---------------------------------------------------------------------------

class Permission(Base):
    """Permission key registry — core permissions and plugin-registered permissions."""

    __tablename__ = "permissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Dot-namespaced key, e.g. 'iam.groups.write' or 'org.bnb.tasks.create'
    key: Mapped[str] = mapped_column(
        String(150), unique=True, nullable=False, index=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Null = core permission; set = belongs to a plugin
    plugin_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    grants: Mapped[list["Grant"]] = relationship(
        "Grant", back_populates="permission", cascade="all, delete-orphan"
    )
    delegations: Mapped[list["Delegation"]] = relationship(
        "Delegation", back_populates="permission", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Permission key={self.key!r}>"


class Grant(Base):
    """Assigns a permission to a user or group, with optional resource scope."""

    __tablename__ = "grants"
    __table_args__ = (
        # Fast lookups: all grants for a particular principal
        Index("ix_grants_principal", "principal_type", "principal_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    principal_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # 'user' | 'group'
    # Polymorphic FK — points to users.id or groups.id depending on principal_type
    principal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    permission_key: Mapped[str] = mapped_column(
        String(150),
        ForeignKey("permissions.key", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Null = global/wildcard scope; set = e.g. 'fork:delhi' or 'plugin:tasks'
    resource_scope: Mapped[str | None] = mapped_column(String(255), nullable=True)
    granted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    permission: Mapped["Permission"] = relationship("Permission", back_populates="grants")

    def __repr__(self) -> str:
        return f"<Grant {self.principal_type}={self.principal_id} key={self.permission_key!r}>"


class Delegation(Base):
    """Temporary delegation of a specific permission from one user to another."""

    __tablename__ = "delegations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    delegator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    delegatee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    permission_key: Mapped[str] = mapped_column(
        String(150),
        ForeignKey("permissions.key", ondelete="CASCADE"),
        nullable=False,
    )
    # Written authority reference (e.g., a Notion page URL or document ID)
    delegation_ref: Mapped[str] = mapped_column(Text, nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    permission: Mapped["Permission"] = relationship("Permission", back_populates="delegations")

    def __repr__(self) -> str:
        return (
            f"<Delegation {self.delegator_id} → {self.delegatee_id} key={self.permission_key!r}>"
        )


# ---------------------------------------------------------------------------
# City Forks
# ---------------------------------------------------------------------------

class Fork(Base):
    """A city-level operational fork (e.g., delhi, bangalore)."""

    __tablename__ = "forks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slug: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )  # e.g. 'delhi', 'bangalore'
    city_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Discord role IDs for this fork (community role + contributor role)
    discord_city_role_id: Mapped[str | None] = mapped_column(String(25), nullable=True)
    discord_contributor_role_id: Mapped[str | None] = mapped_column(String(25), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, name="metadata", default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    members: Mapped[list["ForkMember"]] = relationship(
        "ForkMember", back_populates="fork", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Fork slug={self.slug!r}>"


class ForkMember(Base):
    """Association between a user and a fork, with track and role metadata."""

    __tablename__ = "fork_members"
    __table_args__ = (
        UniqueConstraint("user_id", "fork_id", name="uq_fork_member_user_fork"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fork_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("forks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 'tech' | 'creative' | 'ops' | 'outreach' | null
    track: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 'fork_lead' | 'track_lead' | 'contributor' | 'community'
    local_role: Mapped[str] = mapped_column(String(50), default="contributor", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    left_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship("User", back_populates="fork_memberships")
    fork: Mapped["Fork"] = relationship("Fork", back_populates="members")

    def __repr__(self) -> str:
        return f"<ForkMember user={self.user_id} fork={self.fork_id} role={self.local_role!r}>"


# ---------------------------------------------------------------------------
# Plugin Registry
# ---------------------------------------------------------------------------

class PluginRegistry(Base):
    """Catalogue of installed first- and third-party plugins."""

    __tablename__ = "plugin_registry"

    # Declared plugin ID (e.g., 'org.bnb.tasks') — also serves as PK
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # JSON config blob for plugin-specific settings
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    installed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<PluginRegistry id={self.id!r} version={self.version!r}>"


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------

class AuditLog(Base):
    """
    Append-only audit log for all significant platform actions.

    Records are never updated or deleted — they provide a forensic trail
    across IAM changes, provisioning events, and plugin actions.
    """

    __tablename__ = "audit_log"
    __table_args__ = (
        # Fast time-range queries and actor lookups
        Index("ix_audit_log_created_at", "created_at"),
        Index("ix_audit_log_action", "action"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Dot-namespaced action, e.g. 'iam.grant.created', 'discord.sync.completed'
    action: Mapped[str] = mapped_column(String(150), nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[str] = mapped_column(String(100), nullable=False)
    # Arbitrary JSON context blob
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, name="metadata", default=dict, nullable=False
    )
    # IP address of the request actor (optional, for web-triggered actions)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    # Plugin ID if the action was triggered by a plugin
    plugin_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    actor: Mapped["User | None"] = relationship(
        "User", back_populates="audit_events", foreign_keys=[actor_id]
    )

    def __repr__(self) -> str:
        return f"<AuditLog action={self.action!r} target={self.target_type}:{self.target_id}>"


# ---------------------------------------------------------------------------
# Discord Sync Runs
# ---------------------------------------------------------------------------

class SyncRun(Base):
    """Records each Discord provisioning sync run for observability."""

    __tablename__ = "sync_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # 'scheduled' | 'manual' | 'webhook'
    trigger: Mapped[str] = mapped_column(String(50), nullable=False)
    # 'running' | 'completed' | 'failed'
    status: Mapped[str] = mapped_column(String(20), default="running", nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    members_synced: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    members_added: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    members_removed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errors: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, nullable=False
    )  # list[str]
    discord_member_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    def __repr__(self) -> str:
        return f"<SyncRun id={self.id} status={self.status!r}>"
