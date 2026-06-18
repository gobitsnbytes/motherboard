import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.database import get_session
from app.db.models import AuditLog, PluginRegistry, User


@pytest.fixture(autouse=True)
def override_db(db_session: AsyncSession):
    async def _get_test_session():
        yield db_session
    app.dependency_overrides[get_session] = _get_test_session
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_health_check():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/health/")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_finance_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # /health
        response = await ac.get("/api/finance/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["service"] == "finance"

        # /info
        response = await ac.get("/api/finance/info")
        assert response.status_code == 200
        assert response.json()["status"] == "coming_soon"
        assert "GOBITSNBYTES FOUNDATION" in response.json()["organization"]


@pytest.mark.asyncio
async def test_audit_logs_list_and_filter(db_session: AsyncSession):
    # Create actor
    actor = User(display_name="Audited User")
    db_session.add(actor)
    await db_session.commit()

    # Seed audit logs
    log1 = AuditLog(
        actor_id=actor.id,
        action="test.create",
        target_type="user",
        target_id=str(uuid.uuid4()),
        metadata_json={"val": 1}
    )
    log2 = AuditLog(
        actor_id=actor.id,
        action="test.update",
        target_type="user",
        target_id=str(uuid.uuid4()),
        metadata_json={"val": 2}
    )
    log3 = AuditLog(
        actor_id=None,
        action="system.reset",
        target_type="system",
        target_id="sys",
        metadata_json={"val": 3}
    )
    db_session.add_all([log1, log2, log3])
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # List all (limit = 50)
        response = await ac.get("/api/audit/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 3

        # Limit and offset
        response = await ac.get("/api/audit/?limit=1")
        assert response.status_code == 200
        assert len(response.json()) == 1

        # Filter by action
        response = await ac.get("/api/audit/?action=test.create")
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["action"] == "test.create"

        # Filter by actor_id
        response = await ac.get(f"/api/audit/?actor_id={actor.id}")
        assert response.status_code == 200
        assert len(response.json()) == 2
        for item in response.json():
            assert item["actor_id"] == str(actor.id)


@pytest.mark.asyncio
async def test_plugin_registry_endpoints(db_session: AsyncSession):
    # Seed a plugin
    plugin = PluginRegistry(
        id="org.bnb.testplugin",
        name="Test Plugin",
        version="1.2.3",
        description="A plugin for router testing",
        is_enabled=True,
        config={"theme": "dark"}
    )
    db_session.add(plugin)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # List plugins
        response = await ac.get("/api/plugins/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        names = [p["name"] for p in data]
        assert "Test Plugin" in names

        # Get specific plugin
        response = await ac.get(f"/api/plugins/{plugin.id}")
        assert response.status_code == 200
        assert response.json()["version"] == "1.2.3"
        assert response.json()["config"] == {"theme": "dark"}

        # Get nonexistent plugin (404)
        response = await ac.get("/api/plugins/nonexistent.id")
        assert response.status_code == 404

        # Update plugin settings
        payload = {"is_enabled": False, "config": {"theme": "light"}}
        response = await ac.patch(f"/api/plugins/{plugin.id}", json=payload)
        assert response.status_code == 200
        assert response.json()["is_enabled"] is False
        assert response.json()["config"] == {"theme": "light"}

        # Update nonexistent plugin (404)
        response = await ac.patch("/api/plugins/nonexistent.id", json=payload)
        assert response.status_code == 404
