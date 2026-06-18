import os

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
import json

from app.db.models import Base
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
