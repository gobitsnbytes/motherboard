"""
Shared test fixtures for the BNB API suite.

Two database modes, chosen from DATABASE_URL:

* **Postgres** (CI, and anyone who points DATABASE_URL at one) — the schema is
  built by running ``alembic upgrade head``, exactly like production. This is
  what catches migration drift and Postgres-only behaviour (JSONB operators,
  type strictness, constraint semantics) before it reaches the VPS.
  CI does not run the suite this way: it points the alembic drift checks at
  Postgres and runs the tests on SQLite, which is minutes faster.
* **SQLite** (default, and what CI uses) — the schema is built from
  ``Base.metadata.create_all`` and the Postgres-only column types are compiled
  down to SQLite equivalents. Fast, but it cannot see drift, so CI is the
  authority.
"""

import gc
import hashlib
import hmac
import os
import time
import warnings
from pathlib import Path
from urllib.parse import urlsplit

# Dummy environment variables must exist before app.config is imported.
os.environ.setdefault("DISCORD_CLIENT_ID", "mock_client_id")
os.environ.setdefault("DISCORD_CLIENT_SECRET", "mock_client_secret")
os.environ.setdefault("DISCORD_BOT_TOKEN", "mock_bot_token")
os.environ.setdefault("DISCORD_GUILD_ID", "mock_guild_id")
os.environ["TESTING"] = "True"
# Never report test failures to a real project from a developer .env.
os.environ["SENTRY_DSN"] = ""
os.environ.setdefault("SESSION_SECRET", "mock_session_secret_32_bytes_long_secret_123")
os.environ.setdefault("API_INTERNAL_SECRET", "mock_internal_secret")
os.environ.setdefault("NEXTAUTH_SECRET", "mock_nextauth_secret")
os.environ.setdefault("SPARKCLOUD_API_KEY", "sc-ai-test_key_123")
os.environ.setdefault("INBOUND_EMAIL_WEBHOOK_SECRET", "inbound_sec_8f9a2b4c1d3e5f6g")
os.environ.setdefault("SMTP_PASS", "test_smtp_pass_123")
os.environ.setdefault(
    "DISCORD_CLOUD_APPROVAL_WEBHOOK_URL",
    "https://discord.com/api/webhooks/mock_cloud_approval",
)

SQLITE_DB_FILE = "test_temp_router.db"
_configured_url = os.environ.get("DATABASE_URL", "")
IS_POSTGRES = _configured_url.startswith(
    ("postgres://", "postgresql://", "postgresql+")
)

if not IS_POSTGRES:
    # No Postgres configured: fall back to a throwaway SQLite file.
    if os.path.exists(SQLITE_DB_FILE):
        try:
            os.remove(SQLITE_DB_FILE)
        except OSError:
            pass
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{SQLITE_DB_FILE}"

TEST_DATABASE_URL = os.environ["DATABASE_URL"]

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.db.models  # noqa: F401 — registers every table on Base.metadata
from app.database import get_session
from app.db.models import Base, User
from app.dependencies import canonical_auth_path
from app.main import app

if not IS_POSTGRES:
    # SQLite has no JSONB or native UUID; compile them down so create_all works.
    from sqlalchemy.dialects.postgresql import JSONB
    from sqlalchemy.dialects.postgresql import UUID as PG_UUID
    from sqlalchemy.ext.compiler import compiles

    @compiles(JSONB, "sqlite")
    def compile_jsonb_sqlite(type_, compiler, **kw):
        return "JSON"

    @compiles(PG_UUID, "sqlite")
    def compile_uuid_sqlite(type_, compiler, **kw):
        return "CHAR(36)"


def _run_migrations() -> None:
    """Build the Postgres schema the way production does: alembic upgrade head.

    Called at import time, before pytest-asyncio starts an event loop, because
    alembic/env.py drives its async engine with ``asyncio.run``.
    """
    from alembic import command
    from alembic.config import Config

    api_root = Path(__file__).resolve().parent.parent
    cfg = Config(str(api_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(api_root / "alembic"))
    cfg.set_main_option("skip_logging_config", "True")
    command.upgrade(cfg, "head")


if IS_POSTGRES:
    _run_migrations()

engine = create_async_engine(TEST_DATABASE_URL)
TestingSessionLocal = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def init_session_db():
    if not IS_POSTGRES:
        async with engine.begin() as conn:
            await conn.run_sync(
                lambda sync_conn: Base.metadata.create_all(sync_conn, checkfirst=True)
            )
    yield
    if not IS_POSTGRES:
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all, checkfirst=True)
        except Exception:
            pass
    await engine.dispose()


async def _truncate_all(session: AsyncSession) -> None:
    """Empty every table between tests, ignoring foreign keys while doing so."""
    if IS_POSTGRES:
        # alembic_version is deliberately excluded — dropping it would erase the
        # record of which migrations built this schema.
        tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
        if tables:
            await session.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    else:
        await session.execute(text("PRAGMA foreign_keys = OFF;"))
        for table in Base.metadata.sorted_tables:
            await session.execute(table.delete())
        await session.execute(text("PRAGMA foreign_keys = ON;"))
    await session.commit()


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Point the app at the test engine and hand each test an empty database."""
    import app.database
    from app.config import get_settings

    app.database.get_engine = lambda: engine
    app.database.get_sessionmaker = lambda: TestingSessionLocal
    get_settings.cache_clear()

    if not IS_POSTGRES:
        async with engine.begin() as conn:
            await conn.run_sync(
                lambda sync_conn: Base.metadata.create_all(sync_conn, checkfirst=True)
            )

    async with TestingSessionLocal() as session:
        await _truncate_all(session)
    yield


@pytest.fixture(autouse=True)
def fail_on_unawaited_coroutine():
    """Turn "coroutine ... was never awaited" into a test failure.

    A forgotten ``await`` on an async call is invisible in production — the
    coroutine is created, dropped, and the work silently never happens — and
    pytest reports it only as a warning. Every such warning is a real bug, so
    this fails the test that produced it.
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        yield
        # Unawaited coroutines warn from __del__, so force collection first.
        gc.collect()

    unawaited = sorted(
        {str(w.message) for w in caught if "was never awaited" in str(w.message)}
    )
    for w in caught:
        if "was never awaited" not in str(w.message):
            warnings.warn_explicit(w.message, w.category, w.filename, w.lineno)
    if unawaited:
        raise AssertionError(
            "Coroutine created but never awaited (missing `await`):\n  "
            + "\n  ".join(unawaited)
        )


@pytest_asyncio.fixture
async def db_session():
    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture(autouse=True)
def override_db(db_session: AsyncSession):
    """Route the app's get_session dependency at the test's session.

    Autouse so every test sees the same database its fixtures wrote to. A test
    module that needs different wiring can shadow this with its own
    ``override_db`` fixture.
    """

    async def _get_test_session():
        yield db_session

    app.dependency_overrides[get_session] = _get_test_session
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client():
    """An httpx client bound to the FastAPI app, for request-level tests."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def super_admin(db_session):
    user = User(display_name="Router Super Admin", is_super_admin=True)
    db_session.add(user)
    await db_session.commit()
    return user


def internal_auth_headers(
    user_id, method: str = "GET", path: str = "/"
) -> dict[str, str]:
    timestamp = str(int(time.time()))
    user_id_str = str(user_id)
    secret = os.environ["API_INTERNAL_SECRET"]
    request_path = urlsplit(path).path
    message = (
        f"{timestamp}{method.upper()}{canonical_auth_path(request_path)}{user_id_str}"
    )
    signature = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    return {
        "X-Internal-User-Id": user_id_str,
        "X-Internal-Timestamp": timestamp,
        "X-Internal-Signature": signature,
    }


async def request_as(client, user_id, method: str, path: str, **kwargs):
    headers = {
        **internal_auth_headers(user_id, method=method, path=path),
        **kwargs.pop("headers", {}),
    }
    return await client.request(method, path, headers=headers, **kwargs)


def pytest_sessionfinish(session, exitstatus):
    for suffix in ("", "-journal", "-shm", "-wal"):
        for stem in ("test_temp_router.db", "test_temp_phase1.db"):
            try:
                os.remove(stem + suffix)
            except OSError:
                pass
