"""
Integration tests for Phase 1 — DB schema, seeder, and API routers.

Each test gets a fresh connection that rolls back at the end (savepoint approach).
The engine is created once per session. The seeder runs once before all tests.

Run:
  DATABASE_URL="postgresql+asyncpg://bnb:changeme@localhost:5432/motherboard" \\
  uv run pytest tests/test_phase1.py -v
"""

import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    AsyncTransaction,
    async_sessionmaker,
    create_async_engine,
)

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL or "sqlite" in DATABASE_URL:
    DATABASE_URL = "sqlite+aiosqlite:///test_temp_phase1.db"

# ---------------------------------------------------------------------------
# Session-scoped engine (one connection pool for all tests)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine(DATABASE_URL, pool_pre_ping=True)
    yield eng
    await eng.dispose()


# ---------------------------------------------------------------------------
# Seed data once per session before tests run
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session", autouse=True)
async def seed_once(engine):
    """Run the full seeder before any tests execute."""
    from app.db.models import Base
    
    # If running on SQLite, create tables and insert mock alembic version
    if "sqlite" in engine.url.drivername or "sqlite" in engine.url.database:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
            await conn.execute(text("INSERT OR IGNORE INTO alembic_version (version_num) VALUES ('test_mock_version')"))

    from app.db.seeder import run_seeds
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        await run_seeds(session)


# ---------------------------------------------------------------------------
# Per-test session using SAVEPOINT for cheap rollback isolation
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db(engine) -> AsyncSession:
    """
    Each test runs inside a SAVEPOINT so it can flush/execute SQL
    and be fully rolled back at teardown without touching committed data.
    """
    async with engine.connect() as conn:
        await conn.begin()   # outer transaction
        sess = AsyncSession(bind=conn, expire_on_commit=False)
        yield sess
        await sess.close()
        await conn.rollback()  # roll back everything the test wrote


# ===========================================================================
# 1. Database connectivity
# ===========================================================================

class TestDatabaseConnectivity:
    async def test_can_connect(self, db: AsyncSession) -> None:
        result = await db.execute(text("SELECT 1"))
        assert result.scalar() == 1

    async def test_all_tables_exist(self, db: AsyncSession) -> None:
        expected = {
            "users", "discord_accounts", "groups", "memberships",
            "discord_role_mappings", "permissions", "grants", "delegations",
            "forks", "fork_members", "plugin_registry", "audit_log", "sync_runs",
            "alembic_version",
        }
        if "sqlite" in db.bind.dialect.name:
            result = await db.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
        else:
            result = await db.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
            )
        actual = {row[0] for row in result.fetchall()}
        assert expected.issubset(actual), f"Missing tables: {expected - actual}"

    async def test_alembic_version_set(self, db: AsyncSession) -> None:
        result = await db.execute(text("SELECT version_num FROM alembic_version"))
        version = result.scalar_one_or_none()
        assert version is not None, "No alembic version row found"


# ===========================================================================
# 2. ORM model CRUD
# ===========================================================================

class TestUserModel:
    async def test_create_and_fetch_user(self, db: AsyncSession) -> None:
        from app.db.models import User
        user = User(display_name="Test User", email="test@example.com")
        db.add(user)
        await db.flush()
        fetched = await db.get(User, user.id)
        assert fetched is not None
        assert fetched.display_name == "Test User"
        assert fetched.is_active is True
        assert fetched.is_super_admin is False

    async def test_user_defaults(self, db: AsyncSession) -> None:
        from app.db.models import User
        user = User(display_name="Minimal User")
        db.add(user)
        await db.flush()
        fetched = await db.get(User, user.id)
        assert fetched.email is None
        assert fetched.avatar_url is None
        assert fetched.is_active is True

    async def test_user_soft_delete(self, db: AsyncSession) -> None:
        from app.db.models import User
        user = User(display_name="Deletable User")
        db.add(user)
        await db.flush()
        user.is_active = False
        await db.flush()
        fetched = await db.get(User, user.id)
        assert fetched.is_active is False

    async def test_discord_account_linked(self, db: AsyncSession) -> None:
        from app.db.models import User, DiscordAccount
        user = User(display_name="Discord User")
        db.add(user)
        await db.flush()
        acct = DiscordAccount(
            user_id=user.id,
            discord_id=f"9{uuid.uuid4().int % 10**17}",
            username="discorduser_test",
        )
        db.add(acct)
        await db.flush()
        fetched = await db.get(DiscordAccount, acct.id)
        assert fetched.user_id == user.id


class TestGroupModel:
    async def test_create_group(self, db: AsyncSession) -> None:
        from app.db.models import Group
        slug = f"test-group-{uuid.uuid4().hex[:6]}"
        group = Group(slug=slug, name="Test Group", is_system=False)
        db.add(group)
        await db.flush()
        fetched = await db.get(Group, group.id)
        assert fetched.slug == slug
        assert fetched.is_system is False

    async def test_membership_unique_constraint(self, db: AsyncSession) -> None:
        from sqlalchemy.exc import IntegrityError
        from app.db.models import User, Group, Membership
        user = User(display_name="UQ Test User")
        slug = f"uq-group-{uuid.uuid4().hex[:6]}"
        group = Group(slug=slug, name="UQ Group")
        db.add_all([user, group])
        await db.flush()
        m1 = Membership(user_id=user.id, group_id=group.id, source="manual")
        db.add(m1)
        await db.flush()
        m2 = Membership(user_id=user.id, group_id=group.id, source="manual")
        db.add(m2)
        with pytest.raises(IntegrityError):
            await db.flush()

    async def test_add_user_to_group(self, db: AsyncSession) -> None:
        from app.db.models import User, Group, Membership
        user = User(display_name="Member User")
        slug = f"mem-group-{uuid.uuid4().hex[:6]}"
        group = Group(slug=slug, name="Member Group")
        db.add_all([user, group])
        await db.flush()
        m = Membership(user_id=user.id, group_id=group.id, source="discord_sync")
        db.add(m)
        await db.flush()
        fetched = await db.get(Membership, m.id)
        assert fetched.source == "discord_sync"


class TestGrantModel:
    async def test_create_user_grant(self, db: AsyncSession) -> None:
        from app.db.models import User, Permission, Grant
        user = User(display_name="Grant Test User")
        perm_key = f"test.perm.{uuid.uuid4().hex[:8]}"
        perm = Permission(key=perm_key)
        db.add_all([user, perm])
        await db.flush()
        grant = Grant(principal_type="user", principal_id=user.id, permission_key=perm.key)
        db.add(grant)
        await db.flush()
        fetched = await db.get(Grant, grant.id)
        assert fetched.principal_type == "user"
        assert fetched.resource_scope is None

    async def test_create_scoped_grant(self, db: AsyncSession) -> None:
        from app.db.models import User, Permission, Grant
        user = User(display_name="Scoped Grant User")
        perm_key = f"test.scoped.{uuid.uuid4().hex[:8]}"
        perm = Permission(key=perm_key)
        db.add_all([user, perm])
        await db.flush()
        grant = Grant(
            principal_type="user",
            principal_id=user.id,
            permission_key=perm.key,
            resource_scope="fork:delhi",
        )
        db.add(grant)
        await db.flush()
        fetched = await db.get(Grant, grant.id)
        assert fetched.resource_scope == "fork:delhi"


class TestDelegationModel:
    async def test_create_delegation(self, db: AsyncSession) -> None:
        from app.db.models import User, Permission, Delegation
        u1 = User(display_name="Delegator")
        u2 = User(display_name="Delegatee")
        perm_key = f"test.delegate.{uuid.uuid4().hex[:8]}"
        perm = Permission(key=perm_key)
        db.add_all([u1, u2, perm])
        await db.flush()
        delegation = Delegation(
            delegator_id=u1.id,
            delegatee_id=u2.id,
            permission_key=perm.key,
            delegation_ref="https://notion.so/authority-doc-123",
        )
        db.add(delegation)
        await db.flush()
        fetched = await db.get(Delegation, delegation.id)
        assert fetched.is_revoked is False
        assert "notion.so" in fetched.delegation_ref


class TestForkModel:
    async def test_create_fork(self, db: AsyncSession) -> None:
        from app.db.models import Fork
        slug = f"test-city-{uuid.uuid4().hex[:6]}"
        fork = Fork(slug=slug, city_name="Test City", metadata_json={})
        db.add(fork)
        await db.flush()
        fetched = await db.get(Fork, fork.id)
        assert fetched.city_name == "Test City"
        assert fetched.is_active is True

    async def test_fork_member_with_track(self, db: AsyncSession) -> None:
        from app.db.models import Fork, ForkMember, User
        user = User(display_name="Fork Member")
        slug = f"city2-{uuid.uuid4().hex[:6]}"
        fork = Fork(slug=slug, city_name="City 2", metadata_json={})
        db.add_all([user, fork])
        await db.flush()
        member = ForkMember(user_id=user.id, fork_id=fork.id, local_role="contributor", track="tech")
        db.add(member)
        await db.flush()
        fetched = await db.get(ForkMember, member.id)
        assert fetched.track == "tech"
        assert fetched.is_active is True

    async def test_fork_member_unique_constraint(self, db: AsyncSession) -> None:
        from sqlalchemy.exc import IntegrityError
        from app.db.models import Fork, ForkMember, User
        user = User(display_name="UQ Fork User")
        slug = f"uq-fork-{uuid.uuid4().hex[:6]}"
        fork = Fork(slug=slug, city_name="UQ City", metadata_json={})
        db.add_all([user, fork])
        await db.flush()
        db.add(ForkMember(user_id=user.id, fork_id=fork.id, local_role="contributor"))
        await db.flush()
        db.add(ForkMember(user_id=user.id, fork_id=fork.id, local_role="fork_lead"))
        with pytest.raises(IntegrityError):
            await db.flush()


class TestSyncRun:
    async def test_create_sync_run(self, db: AsyncSession) -> None:
        from app.db.models import SyncRun
        run = SyncRun(trigger="manual", status="running")
        db.add(run)
        await db.flush()
        fetched = await db.get(SyncRun, run.id)
        assert fetched.trigger == "manual"
        assert fetched.status == "running"
        assert fetched.members_synced == 0
        assert fetched.errors == []


class TestPluginRegistry:
    async def test_create_plugin(self, db: AsyncSession) -> None:
        from app.db.models import PluginRegistry
        pid = f"org.bnb.test.{uuid.uuid4().hex[:6]}"
        plugin = PluginRegistry(id=pid, name="Test Plugin", version="1.0.0", config={"key": "val"})
        db.add(plugin)
        await db.flush()
        fetched = await db.get(PluginRegistry, pid)
        assert fetched.name == "Test Plugin"
        assert fetched.is_enabled is True
        assert fetched.config == {"key": "val"}


# ===========================================================================
# 3. Seeder validation (reads committed data from before-tests setup)
# ===========================================================================

class TestSeeder:
    async def test_system_groups_seeded(self, db: AsyncSession) -> None:
        from app.db.models import Group
        result = await db.execute(select(Group).where(Group.is_system.is_(True)))
        slugs = {g.slug for g in result.scalars().all()}
        required = {"sg_super_admin", "sg_contributor", "sg_fork_lead", "sg_executive", "sg_hq"}
        assert required.issubset(slugs), f"Missing: {required - slugs}"

    async def test_system_groups_count(self, db: AsyncSession) -> None:
        from app.db.models import Group
        result = await db.execute(select(Group).where(Group.is_system.is_(True)))
        assert len(result.scalars().all()) >= 15

    async def test_core_permissions_seeded(self, db: AsyncSession) -> None:
        from app.db.models import Permission
        result = await db.execute(select(Permission))
        keys = {p.key for p in result.scalars().all()}
        required = {"iam.users.read", "iam.grants.write", "forks.read", "audit.read", "provisioning.sync.trigger"}
        assert required.issubset(keys), f"Missing: {required - keys}"

    async def test_permission_is_core(self, db: AsyncSession) -> None:
        from app.db.models import Permission
        result = await db.execute(select(Permission).where(Permission.key == "iam.users.read"))
        perm = result.scalar_one()
        assert perm.plugin_id is None

    async def test_discord_role_mappings_seeded(self, db: AsyncSession) -> None:
        from app.db.models import DiscordRoleMapping
        result = await db.execute(select(DiscordRoleMapping))
        ids = {m.discord_role_id for m in result.scalars().all()}
        assert "1506019068132462804" in ids  # Contributor
        assert "1480620981587279993" in ids  # Admin

    async def test_city_forks_seeded(self, db: AsyncSession) -> None:
        from app.db.models import Fork
        result = await db.execute(select(Fork))
        slugs = {f.slug for f in result.scalars().all()}
        assert {"delhi", "bangalore", "hyderabad", "kolkata"}.issubset(slugs)

    async def test_seeder_idempotent(self, db: AsyncSession) -> None:
        """Running seeder again should not create duplicate permissions."""
        from app.db.models import Permission
        from app.db.seeder import run_seeds
        # Run again in this test's transaction (rolled back after)
        await run_seeds(db)
        result = await db.execute(
            select(Permission).where(Permission.key == "iam.users.read")
        )
        rows = result.scalars().all()
        assert len(rows) == 1, f"Expected 1, got {len(rows)}"


# ===========================================================================
# 4. AuditLog
# ===========================================================================

class TestAuditLog:
    async def test_audit_log_insert(self, db: AsyncSession) -> None:
        from app.db.models import AuditLog
        entry = AuditLog(
            action="test.action",
            target_type="user",
            target_id=str(uuid.uuid4()),
            metadata_json={"test": True},
        )
        db.add(entry)
        await db.flush()
        fetched = await db.get(AuditLog, entry.id)
        assert fetched.action == "test.action"
        assert fetched.metadata_json == {"test": True}
        assert fetched.ip_address is None

    async def test_audit_log_with_actor(self, db: AsyncSession) -> None:
        from app.db.models import AuditLog, User
        user = User(display_name="Auditor")
        db.add(user)
        await db.flush()
        entry = AuditLog(
            actor_id=user.id,
            action="iam.grant.created",
            target_type="grant",
            target_id=str(uuid.uuid4()),
            metadata_json={"permission_key": "forks.read"},
            ip_address="127.0.0.1",
        )
        db.add(entry)
        await db.flush()
        fetched = await db.get(AuditLog, entry.id)
        assert fetched.actor_id == user.id
        assert fetched.ip_address == "127.0.0.1"
