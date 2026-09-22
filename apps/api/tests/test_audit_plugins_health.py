import uuid
import asyncio
from types import SimpleNamespace

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog, PluginRegistry, User
from conftest import request_as


async def test_health_check(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-request-id"]


async def test_request_id_accepts_only_safe_values(client):
    response = await client.get("/health", headers={"X-Request-ID": "login-check-42"})
    assert response.headers["x-request-id"] == "login-check-42"

    response = await client.get("/health", headers={"X-Request-ID": "bad value"})
    assert response.headers["x-request-id"] != "bad value"


async def test_finance_endpoints(client):
    # /health
    response = await client.get("/api/finance/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "finance"

    # /info
    response = await client.get("/api/finance/info")
    assert response.status_code == 200
    assert response.json()["status"] == "active"
    assert "GOBITSNBYTES FOUNDATION" in response.json()["organization"]


async def test_audit_logs_list_and_filter(
    db_session: AsyncSession, super_admin: User, client
):
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
        metadata_json={"val": 1},
    )
    log2 = AuditLog(
        actor_id=actor.id,
        action="test.update",
        target_type="user",
        target_id=str(uuid.uuid4()),
        metadata_json={"val": 2},
    )
    log3 = AuditLog(
        actor_id=None,
        action="system.reset",
        target_type="system",
        target_id="sys",
        metadata_json={"val": 3},
    )
    db_session.add_all([log1, log2, log3])
    await db_session.commit()

    # List all (limit = 50)
    response = await request_as(client, super_admin.id, "GET", "/api/audit/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 3

    # Limit and offset
    response = await request_as(client, super_admin.id, "GET", "/api/audit/?limit=1")
    assert response.status_code == 200
    assert len(response.json()) == 1

    # Filter by action
    response = await request_as(
        client, super_admin.id, "GET", "/api/audit/?action=test.create"
    )
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["action"] == "test.create"

    # Filter by actor_id
    response = await request_as(
        client, super_admin.id, "GET", f"/api/audit/?actor_id={actor.id}"
    )
    assert response.status_code == 200
    assert len(response.json()) == 2
    for item in response.json():
        assert item["actor_id"] == str(actor.id)


async def test_plugin_registry_endpoints(
    db_session: AsyncSession, super_admin: User, client
):
    # Seed a plugin
    plugin = PluginRegistry(
        id="org.bnb.testplugin",
        name="Test Plugin",
        version="1.2.3",
        description="A plugin for router testing",
        is_enabled=True,
        config={"theme": "dark"},
    )
    db_session.add(plugin)
    await db_session.commit()

    # List plugins
    response = await request_as(client, super_admin.id, "GET", "/api/plugins/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    names = [p["name"] for p in data]
    assert "Test Plugin" in names

    # Get specific plugin
    response = await request_as(
        client, super_admin.id, "GET", f"/api/plugins/{plugin.id}"
    )
    assert response.status_code == 200
    assert response.json()["version"] == "1.2.3"
    assert response.json()["config"] == {"theme": "dark"}

    # Get nonexistent plugin (404)
    response = await request_as(
        client, super_admin.id, "GET", "/api/plugins/nonexistent.id"
    )
    assert response.status_code == 404

    # Update plugin settings
    payload = {"is_enabled": False, "config": {"theme": "light"}}
    response = await request_as(
        client, super_admin.id, "PATCH", f"/api/plugins/{plugin.id}", json=payload
    )
    assert response.status_code == 200
    assert response.json()["is_enabled"] is False
    assert response.json()["config"] == {"theme": "light"}

    # Update nonexistent plugin (404)
    response = await request_as(
        client, super_admin.id, "PATCH", "/api/plugins/nonexistent.id", json=payload
    )
    assert response.status_code == 404


async def test_health_ready(client):
    response = await client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "healthy"
    assert data["redis"] == "healthy"


async def test_detailed_status(super_admin: User, client, monkeypatch):
    from app.routers import health

    monkeypatch.setattr(
        health,
        "get_settings",
        lambda: SimpleNamespace(
            discord_bot_token="",
            discord_guild_id="",
            app_version="test",
        ),
    )
    response = await request_as(client, super_admin.id, "GET", "/api/health/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "database" in data
    assert "redis" in data
    assert "discord" in data
    assert "sync" in data


async def test_detailed_status_returns_partial_result_when_database_times_out(
    monkeypatch,
):
    from app.routers import health

    class SlowDb:
        async def execute(self, _statement):
            await asyncio.sleep(0.05)

        async def scalar(self, _statement):
            await asyncio.sleep(0.05)

    monkeypatch.setattr(health, "DB_TIMEOUT_SECONDS", 0.001)
    monkeypatch.setattr(health.event_bus, "redis", None)
    monkeypatch.setattr(
        health,
        "get_settings",
        lambda: SimpleNamespace(
            discord_bot_token="",
            discord_guild_id="",
            app_version="test",
        ),
    )

    data = await health.get_detailed_status(SlowDb())

    assert data["status"] == "degraded"
    assert data["database"] == "unhealthy"
    assert data["redis"] == "unconfigured"
    assert data["discord"] == "unconfigured"
    assert data["sync"] == "unknown"
