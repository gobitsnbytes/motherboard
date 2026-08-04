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
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
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
        JSON, name="metadata", default=dict, nullable=False
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
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
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
        JSON, name="metadata", default=dict, nullable=False
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
        JSON, default=list, nullable=False
    )  # list[str]
    discord_member_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    def __repr__(self) -> str:
        return f"<SyncRun id={self.id} status={self.status!r}>"


# ---------------------------------------------------------------------------
# Finance — Virtual Accounts, Cards, Money Requests
# ---------------------------------------------------------------------------

class VirtualAccount(Base):
    """
    Paper virtual bank account. All balances are internal ledger values only —
    no real money moves. One real current account sits underneath the entire system.
    """

    __tablename__ = "virtual_accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Balance stored in paise (₹1 = 100 paise) to avoid float rounding
    balance_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Human-readable fake account identifiers
    account_number: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    ifsc: Mapped[str] = mapped_column(String(11), default="GOBN0001001", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, name="metadata", default=dict, nullable=False
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

    owner: Mapped["User"] = relationship("User", foreign_keys=[owner_id])
    cards: Mapped[list["VirtualCard"]] = relationship(
        "VirtualCard", back_populates="account", cascade="all, delete-orphan"
    )
    outgoing_requests: Mapped[list["MoneyRequest"]] = relationship(
        "MoneyRequest", back_populates="from_account", foreign_keys="MoneyRequest.from_account_id"
    )
    incoming_requests: Mapped[list["MoneyRequest"]] = relationship(
        "MoneyRequest", back_populates="to_account", foreign_keys="MoneyRequest.to_account_id"
    )
    debits: Mapped[list["VirtualTransaction"]] = relationship(
        "VirtualTransaction", back_populates="source_account", foreign_keys="VirtualTransaction.source_account_id"
    )
    credits: Mapped[list["VirtualTransaction"]] = relationship(
        "VirtualTransaction", back_populates="destination_account", foreign_keys="VirtualTransaction.destination_account_id"
    )

    def __repr__(self) -> str:
        return f"<VirtualAccount id={self.id} name={self.name!r}>"


class VirtualCard(Base):
    """
    A virtual card attached to a VirtualAccount. Cosmetic / tracking only —
    no real payment rails behind it.
    """

    __tablename__ = "virtual_cards"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("virtual_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    holder_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    card_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Stored last four digits only — full number never persisted
    last_four: Mapped[str] = mapped_column(String(4), nullable=False)
    # 'virtual' | 'debit'
    card_type: Mapped[str] = mapped_column(String(20), default="virtual", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expires_month: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_year: Mapped[int] = mapped_column(Integer, nullable=False)
    # Card limits in paise (optional)
    daily_limit_paise: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    monthly_limit_paise: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    account: Mapped["VirtualAccount"] = relationship("VirtualAccount", back_populates="cards")
    holder: Mapped["User"] = relationship("User", foreign_keys=[holder_id])

    def __repr__(self) -> str:
        return f"<VirtualCard id={self.id} last_four={self.last_four!r} type={self.card_type!r} daily_limit={self.daily_limit_paise}>"


class MoneyRequest(Base):
    """
    A paper money request — either from the main pool (from_account_id=None)
    or from a specific VirtualAccount to another. Approved requests adjust
    both account balances; no real funds move.
    """

    __tablename__ = "money_requests"
    __table_args__ = (
        Index("ix_money_requests_status", "status"),
        Index("ix_money_requests_requester", "requester_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Null → draw from the single main pool / treasury
    from_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("virtual_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    to_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("virtual_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requester_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Amount in paise
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # 'pending' | 'approved' | 'rejected'
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    from_account: Mapped["VirtualAccount | None"] = relationship(
        "VirtualAccount", back_populates="outgoing_requests", foreign_keys=[from_account_id]
    )
    to_account: Mapped["VirtualAccount"] = relationship(
        "VirtualAccount", back_populates="incoming_requests", foreign_keys=[to_account_id]
    )
    requester: Mapped["User"] = relationship("User", foreign_keys=[requester_id])
    reviewer: Mapped["User | None"] = relationship("User", foreign_keys=[reviewed_by])

    def __repr__(self) -> str:
        return f"<MoneyRequest id={self.id} status={self.status!r} amount={self.amount_paise}>"


class VirtualTransaction(Base):
    """
    A paper money transaction tracking historical flows of money (debits and credits)
    between accounts or from/to the treasury pool.
    """

    __tablename__ = "virtual_transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("virtual_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    destination_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("virtual_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    # 'money_request' | 'card_charge' | 'manual_adjustment'
    reference_type: Mapped[str] = mapped_column(String(30), nullable=False)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    source_account: Mapped["VirtualAccount | None"] = relationship(
        "VirtualAccount", back_populates="debits", foreign_keys=[source_account_id]
    )
    destination_account: Mapped["VirtualAccount | None"] = relationship(
        "VirtualAccount", back_populates="credits", foreign_keys=[destination_account_id]
    )

    def __repr__(self) -> str:
        return f"<VirtualTransaction id={self.id} amount={self.amount_paise} type={self.reference_type!r}>"


# ---------------------------------------------------------------------------
# Discord Bot Tables
# ---------------------------------------------------------------------------

class BotMeeting(Base):
    __tablename__ = "meetings"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_time: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_type: Mapped[str] = mapped_column(String(100), nullable=False)
    location_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    temp_channel_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    creator_id: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    calcom_booking_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    calcom_uid: Mapped[str | None] = mapped_column(String(255), nullable=True)
    end_time: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    external_emails: Mapped[str | None] = mapped_column(Text, nullable=True)
    recording_status: Mapped[str] = mapped_column(String(50), default="none", server_default="none", nullable=False)
    meet_code: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    booked_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    scope: Mapped[str] = mapped_column(String(50), default="invite", server_default="invite", nullable=False)
    activated_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class UserAvailability(Base):
    __tablename__ = "user_availability"

    discord_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timezone: Mapped[str] = mapped_column(String(100), default="Asia/Kolkata", server_default="Asia/Kolkata", nullable=False)
    weekly_hours: Mapped[str | None] = mapped_column(Text, nullable=True)
    booking_link: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    calcom_event_type_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    associated_role_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    avatar: Mapped[str | None] = mapped_column(String(500), nullable=True)


class PendingNotionProfile(Base):
    __tablename__ = "pending_notion_profiles"

    discord_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    city: Mapped[str] = mapped_column(String(100), primary_key=True)
    assigned_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    last_reminded_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", server_default="pending", nullable=False)


class MeetingEmailPreference(Base):
    __tablename__ = "meeting_email_preferences"

    discord_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    notify_on_invite: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    notify_on_reminder: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


class WebSession(Base):
    __tablename__ = "web_sessions"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    avatar: Mapped[str | None] = mapped_column(String(500), nullable=True)


class BotJobRun(Base):
    __tablename__ = "bot_job_runs"

    job_name: Mapped[str] = mapped_column(String(255), primary_key=True)
    period_key: Mapped[str] = mapped_column(String(255), primary_key=True)
    ran_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


class MeetingAttendee(Base):
    __tablename__ = "meeting_attendees"

    meeting_id: Mapped[str] = mapped_column(String(255), ForeignKey("meetings.id", ondelete="CASCADE"), primary_key=True)
    attendee_type: Mapped[str] = mapped_column(String(100), primary_key=True)
    discord_id: Mapped[str] = mapped_column(String(100), primary_key=True)


class MeetingReminderSent(Base):
    __tablename__ = "meeting_reminders_sent"

    meeting_id: Mapped[str] = mapped_column(String(255), ForeignKey("meetings.id", ondelete="CASCADE"), primary_key=True)
    reminder_type: Mapped[str] = mapped_column(String(100), primary_key=True)
    sent_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


class MeetingAttendancePing(Base):
    __tablename__ = "meeting_attendance_pings"

    meeting_id: Mapped[str] = mapped_column(String(255), ForeignKey("meetings.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    last_ping_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


class MeetingTranscript(Base):
    __tablename__ = "meeting_transcripts"

    meeting_id: Mapped[str] = mapped_column(String(255), ForeignKey("meetings.id", ondelete="CASCADE"), primary_key=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_decisions: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_items: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamped_transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    vc_text_messages: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    speaker_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processed_at: Mapped[str | None] = mapped_column(String(100), nullable=True)


class MeetingRescheduleHistory(Base):
    __tablename__ = "meeting_reschedule_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meeting_id: Mapped[str] = mapped_column(String(255), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    old_scheduled_time: Mapped[int] = mapped_column(BigInteger, nullable=False)
    old_end_time: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    new_scheduled_time: Mapped[int] = mapped_column(BigInteger, nullable=False)
    new_end_time: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    rescheduled_by: Mapped[str] = mapped_column(String(100), nullable=False)
    rescheduled_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    endpoint: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    p256dh: Mapped[str] = mapped_column(Text, nullable=False)
    auth: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


class ActionItem(Base):
    __tablename__ = "action_items"
    __table_args__ = (
        Index("idx_action_items_discord_status", "discord_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meeting_id: Mapped[str] = mapped_column(String(255), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    assignee: Mapped[str] = mapped_column(String(255), nullable=False)
    discord_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    task: Mapped[str] = mapped_column(Text, nullable=False)
    deadline: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", server_default="pending", nullable=False)
    notified_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


class TeamMemberCache(Base):
    __tablename__ = "team_members"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    fork_id: Mapped[str] = mapped_column(String(100), nullable=False)
    discord_id: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    joined_date: Mapped[str] = mapped_column(String(100), nullable=False)


class EventCache(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    fork_id: Mapped[str] = mapped_column(String(100), nullable=False)
    date: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_attendees: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    actual_attendees: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    calcom_booking_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    calcom_uid: Mapped[str | None] = mapped_column(String(255), nullable=True)


class ReportCache(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    fork_id: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    submitted_date: Mapped[str] = mapped_column(String(100), nullable=False)
    attachment_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(100), nullable=False)


class BotSetting(Base):
    __tablename__ = "bot_settings"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    val: Mapped[str | None] = mapped_column(Text, nullable=True)


# ---------------------------------------------------------------------------
# Dyslexic — Sponsorship & Outreach
# ---------------------------------------------------------------------------

class DyslexicCompany(Base):
    """A prospective sponsor. Research is AI-generated and advisory only."""

    __tablename__ = "dyslexic_companies"
    __table_args__ = (
        Index("ix_dyslexic_companies_stage", "stage"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Lowercased, scheme/www/path stripped. Unique so the same sponsor cannot
    # be added twice. Null when no website was supplied.
    normalized_domain: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True, index=True
    )
    stage: Mapped[str] = mapped_column(String(30), default="research", nullable=False)
    research_status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )
    research_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    # Model output kept verbatim when JSON parsing fails, so a bad response is
    # debuggable instead of lost.
    research_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    research_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    research_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    research_model: Mapped[str | None] = mapped_column(String(60), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    added_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    fork_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("forks.id", ondelete="SET NULL"), nullable=True
    )
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    contacts: Mapped[list["DyslexicContact"]] = relationship(
        "DyslexicContact", back_populates="company", cascade="all, delete-orphan"
    )
    adder: Mapped["User | None"] = relationship("User", foreign_keys=[added_by])

    def __repr__(self) -> str:
        return f"<DyslexicCompany name={self.name!r} stage={self.stage!r}>"


class DyslexicContact(Base):
    """A person at a prospective sponsor, and the outreach state for them."""

    __tablename__ = "dyslexic_contacts"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "email", name="uq_dyslexic_contact_company_email"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dyslexic_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    role: Mapped[str | None] = mapped_column(String(150), nullable=True)
    # Always stored lowercased so uniqueness is case-insensitive in practice.
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="new", nullable=False)
    # Set once at the first send and never overwritten — this is the record of
    # who owns this outreach.
    contacted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    contacted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Soft claim while drafting. Expires on its own; no cleanup job.
    claimed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    claim_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    added_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    company: Mapped["DyslexicCompany"] = relationship(
        "DyslexicCompany", back_populates="contacts"
    )
    contacter: Mapped["User | None"] = relationship("User", foreign_keys=[contacted_by])
    claimer: Mapped["User | None"] = relationship("User", foreign_keys=[claimed_by])
    adder: Mapped["User | None"] = relationship("User", foreign_keys=[added_by])

    def __repr__(self) -> str:
        return f"<DyslexicContact name={self.name!r} status={self.status!r}>"


class DyslexicEmail(Base):
    """A generated draft. Kept whether or not it was ever sent."""

    __tablename__ = "dyslexic_emails"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dyslexic_contacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dyslexic_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(20), default="initial", nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    tone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    extra_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(60), nullable=True)
    generated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<DyslexicEmail contact={self.contact_id} kind={self.kind!r}>"


class DyslexicOutreach(Base):
    """One 'I've Sent Email' click. The duplicate guard lives here."""

    __tablename__ = "dyslexic_outreach"
    __table_args__ = (
        # At most one initial email per contact, enforced by the database so a
        # race between two volunteers cannot produce two.
        Index(
            "uq_dyslexic_outreach_initial_per_contact",
            "contact_id",
            unique=True,
            postgresql_where=text("kind = 'initial'"),
            sqlite_where=text("kind = 'initial'"),
        ),
        Index("ix_dyslexic_outreach_sent_by_kind", "sent_by", "kind"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dyslexic_contacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dyslexic_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Null when the volunteer wrote the email themselves instead of generating.
    email_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dyslexic_emails.id", ondelete="SET NULL"),
        nullable=True,
    )
    kind: Mapped[str] = mapped_column(String(20), default="initial", nullable=False)
    sent_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    outcome: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    outcome_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    outcome_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    outcome_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<DyslexicOutreach contact={self.contact_id} kind={self.kind!r}>"


class DyslexicFollowUp(Base):
    """A reminder to chase. At most one pending per contact."""

    __tablename__ = "dyslexic_follow_ups"
    __table_args__ = (
        Index(
            "ix_dyslexic_follow_ups_assignee_due", "assigned_to", "status", "due_at"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    outreach_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dyslexic_outreach.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dyslexic_contacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dyslexic_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<DyslexicFollowUp contact={self.contact_id} due={self.due_at}>"


class DyslexicEvent(Base):
    """
    Per-company product timeline.

    Distinct from audit_log, which stays a platform-wide forensic record
    indexed by action rather than by company. Both are written; they serve
    different readers.
    """

    __tablename__ = "dyslexic_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dyslexic_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dyslexic_contacts.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    summary: Mapped[str] = mapped_column(String(300), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, name="metadata", default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    actor: Mapped["User | None"] = relationship("User", foreign_keys=[actor_id])

    def __repr__(self) -> str:
        return f"<DyslexicEvent kind={self.kind!r} company={self.company_id}>"


# ---------------------------------------------------------------------------
# Digital Signatures System (bnb-signatures)
# ---------------------------------------------------------------------------

class SignatureRequest(Base):
    """Master record for a digital signature contract request."""
    __tablename__ = "signature_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)  # draft, pending, completed, voided, expired
    original_file_path: Mapped[str] = mapped_column(Text, nullable=False)
    signed_file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)  # SHA-256
    idempotency_key: Mapped[str | None] = mapped_column(String(100), unique=True, index=True, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    recipients: Mapped[list["SignatureRecipient"]] = relationship("SignatureRecipient", back_populates="request", cascade="all, delete-orphan", order_by="SignatureRecipient.signing_order")
    fields: Mapped[list["SignatureField"]] = relationship("SignatureField", back_populates="request", cascade="all, delete-orphan")
    audit_logs: Mapped[list["SignatureAuditLog"]] = relationship("SignatureAuditLog", back_populates="request", cascade="all, delete-orphan", order_by="SignatureAuditLog.created_at")


class SignatureRecipient(Base):
    """Signatory or viewer associated with a signature request."""
    __tablename__ = "signature_recipients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("signature_requests.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="signer", nullable=False)  # signer, viewer, cc
    signing_order: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)  # pending, sent, viewed, signed, declined
    access_token: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    access_passcode: Mapped[str | None] = mapped_column(String(50), nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    request: Mapped["SignatureRequest"] = relationship("SignatureRequest", back_populates="recipients")
    fields: Mapped[list["SignatureField"]] = relationship("SignatureField", back_populates="recipient", cascade="all, delete-orphan")


class SignatureField(Base):
    """Interactive field overlay placed on document page canvas."""
    __tablename__ = "signature_fields"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("signature_requests.id", ondelete="CASCADE"), nullable=False)
    recipient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("signature_recipients.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # signature, fullname, date, text, checkbox
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-indexed
    pos_x: Mapped[float] = mapped_column(Float, nullable=False)  # percentage (0-100)
    pos_y: Mapped[float] = mapped_column(Float, nullable=False)  # percentage (0-100)
    width: Mapped[float] = mapped_column(Float, nullable=False)  # percentage (0-100)
    height: Mapped[float] = mapped_column(Float, nullable=False)  # percentage (0-100)
    required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)  # filled text / signature base64 image data URL

    # Relationships
    request: Mapped["SignatureRequest"] = relationship("SignatureRequest", back_populates="fields")
    recipient: Mapped["SignatureRecipient"] = relationship("SignatureRecipient", back_populates="fields")


class SignatureAuditLog(Base):
    """Immutable event log for all signature workflow steps."""
    __tablename__ = "signature_audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("signature_requests.id", ondelete="CASCADE"), nullable=False)
    recipient_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("signature_recipients.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)  # created, sent, viewed, signed, declined, completed, voided
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    request: Mapped["SignatureRequest"] = relationship("SignatureRequest", back_populates="audit_logs")


class ContractAssistantContract(Base):
    """Internal Contract Assistant reviewed contracts."""
    __tablename__ = "ca_contracts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    counterparty: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="in_review", nullable=False)  # in_review, out_for_signature, dotted, archived
    value: Mapped[str | None] = mapped_column(String(100), nullable=True)
    original_file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_id: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)  # Deduplication for inbound email
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    clauses: Mapped[list["ContractAssistantClause"]] = relationship("ContractAssistantClause", back_populates="contract", cascade="all, delete-orphan")
    findings: Mapped[list["ContractAssistantFinding"]] = relationship("ContractAssistantFinding", back_populates="contract", cascade="all, delete-orphan")
    signatories: Mapped[list["ContractAssistantSignatory"]] = relationship("ContractAssistantSignatory", back_populates="contract", cascade="all, delete-orphan")
    envelopes: Mapped[list["ContractAssistantEnvelope"]] = relationship("ContractAssistantEnvelope", back_populates="contract", cascade="all, delete-orphan")
    events: Mapped[list["ContractAssistantEvent"]] = relationship("ContractAssistantEvent", back_populates="contract", cascade="all, delete-orphan")


class ContractAssistantClause(Base):
    """Parsed clauses of a contract."""
    __tablename__ = "ca_clauses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contract_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ca_contracts.id", ondelete="CASCADE"), nullable=False)
    ref: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., §4.2
    heading: Mapped[str] = mapped_column(String(255), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Relationships
    contract: Mapped["ContractAssistantContract"] = relationship("ContractAssistantContract", back_populates="clauses")
    findings: Mapped[list["ContractAssistantFinding"]] = relationship("ContractAssistantFinding", back_populates="clause", cascade="all, delete-orphan")


class ContractAssistantFinding(Base):
    """Merged findings list (Rule Engine + LLM Risk Pass)."""
    __tablename__ = "ca_findings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contract_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ca_contracts.id", ondelete="CASCADE"), nullable=False)
    clause_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ca_clauses.id", ondelete="CASCADE"), nullable=True)
    clause_ref: Mapped[str] = mapped_column(String(50), nullable=False)
    heading: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)  # rule_engine | llm_judgment
    severity: Mapped[str] = mapped_column(String(50), nullable=False)  # high | medium | low
    risk_type: Mapped[str] = mapped_column(String(100), nullable=False)
    plain_english: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_action: Mapped[str] = mapped_column(Text, nullable=False)
    policy_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_fix: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_rewrite: Mapped[str | None] = mapped_column(Text, nullable=True)
    tier: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # 1 = Template swap, 2 = LLM redline
    status: Mapped[str] = mapped_column(String(50), default="open", nullable=False)  # open, resolved, dismissed
    dismissed_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    contract: Mapped["ContractAssistantContract"] = relationship("ContractAssistantContract", back_populates="findings")
    clause: Mapped["ContractAssistantClause"] = relationship("ContractAssistantClause", back_populates="findings")


class ContractAssistantSignatory(Base):
    """Signatory tracked for contract assistant dispatch."""
    __tablename__ = "ca_signatories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contract_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ca_contracts.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="signer", nullable=False)
    envelope_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)

    # Relationships
    contract: Mapped["ContractAssistantContract"] = relationship("ContractAssistantContract", back_populates="signatories")


class ContractAssistantEnvelope(Base):
    """Linked bnb-signatures request envelope."""
    __tablename__ = "ca_envelopes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contract_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ca_contracts.id", ondelete="CASCADE"), nullable=False)
    signature_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("signature_requests.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    contract: Mapped["ContractAssistantContract"] = relationship("ContractAssistantContract", back_populates="envelopes")
    signature_request: Mapped["SignatureRequest"] = relationship("SignatureRequest")


class ContractAssistantEvent(Base):
    """Audit event trail for Contract Assistant actions."""
    __tablename__ = "ca_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contract_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ca_contracts.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(100), nullable=False)  # ingested, analyzed, fix_applied, finding_dismissed, dispatched
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    contract: Mapped["ContractAssistantContract"] = relationship("ContractAssistantContract", back_populates="events")


>>>>>>> origin/prod
