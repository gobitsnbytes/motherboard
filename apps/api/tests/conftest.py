import hashlib
import hmac
import os
import time
from urllib.parse import urlsplit

# Set dummy environment variables for tests before importing app config
os.environ.setdefault("DISCORD_CLIENT_ID", "mock_client_id")
os.environ.setdefault("DISCORD_CLIENT_SECRET", "mock_client_secret")
os.environ.setdefault("DISCORD_BOT_TOKEN", "mock_bot_token")
os.environ.setdefault("DISCORD_GUILD_ID", "mock_guild_id")
os.environ["TESTING"] = "True"
db_url = os.environ.get("DATABASE_URL")
if not db_url or "sqlite" in db_url:
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///test_temp_router.db"
os.environ.setdefault("SESSION_SECRET", "mock_session_secret_32_bytes_long_secret_123")
os.environ.setdefault("API_INTERNAL_SECRET", "mock_internal_secret")
os.environ.setdefault("NEXTAUTH_SECRET", "mock_nextauth_secret")

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base, User
from app.dependencies import canonical_auth_path
from sqlalchemy.dialects.postgresql import JSONB

# Sqlite doesn't support JSONB natively, let's mock it for tests
from sqlalchemy.ext.compiler import compiles

@compiles(JSONB, 'sqlite')
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

TEST_DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_async_engine(TEST_DATABASE_URL)
TestingSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

@pytest_asyncio.fixture(scope="session", autouse=True)
async def cleanup_engine():
    yield
    await engine.dispose()

@pytest_asyncio.fixture(autouse=True)
async def setup_db(request):
    # Clear DB engine cache and config settings cache
    from app.database import clear_db_cache
    from app.config import get_settings
    clear_db_cache()
    get_settings.cache_clear()

    # Skip setup/teardown if the test is in test_phase1 to avoid interference
    if "test_phase1" in request.module.__name__:
        yield
        return

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture
async def db_session():
    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def super_admin(db_session):
    user = User(display_name="Router Super Admin", is_super_admin=True)
    db_session.add(user)
    await db_session.commit()
    return user


def internal_auth_headers(user_id, method: str = "GET", path: str = "/") -> dict[str, str]:
    timestamp = str(int(time.time()))
    user_id_str = str(user_id)
    secret = os.environ["API_INTERNAL_SECRET"]
    request_path = urlsplit(path).path
    message = f"{timestamp}{method.upper()}{canonical_auth_path(request_path)}{user_id_str}"
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
    import os
    for temp_file in [
        "test_temp_router.db",
        "test_temp_phase1.db",
        "test_temp_router.db-journal",
        "test_temp_phase1.db-journal",
        "test_temp_router.db-shm",
        "test_temp_phase1.db-shm",
        "test_temp_router.db-wal",
        "test_temp_phase1.db-wal"
    ]:
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except Exception:
            pass
