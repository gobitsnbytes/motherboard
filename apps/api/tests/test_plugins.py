import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.main import app
from app.database import get_session
from app.db.models import PluginRegistry, Permission, User
from app.plugin_sdk.loader import PluginLoader
from app.plugin_sdk.types import PluginManifest, PermissionDeclaration, UiPanelDeclaration, PluginContext
from conftest import request_as
from fastapi import APIRouter, FastAPI


@pytest.fixture(autouse=True)
def override_db(db_session: AsyncSession):
    async def _get_test_session():
        yield db_session
    app.dependency_overrides[get_session] = _get_test_session
    yield
    app.dependency_overrides.clear()


# Mock Router and Lifecycle Hooks
mock_router = APIRouter()


@mock_router.get("/test-endpoint")
async def test_endpoint():
    return {"message": "Success"}


on_load_called = False
on_unload_called = False


async def mock_on_load(app_inst: FastAPI, ctx: PluginContext):
    global on_load_called
    on_load_called = True


async def mock_on_unload(ctx: PluginContext):
    global on_unload_called
    on_unload_called = True


def make_test_manifest(plugin_id: str = "test_plugin", is_enabled: bool = True) -> PluginManifest:
    return PluginManifest(
        id=plugin_id,
        name="Test Dynamic Plugin",
        version="1.0.0",
        description="A plugin for unit testing loader logic",
        router=mock_router,
        on_load=mock_on_load,
        on_unload=mock_on_unload,
        permissions=[
            PermissionDeclaration(key=f"{plugin_id}.read", description="Read plugin data"),
        ],
        ui_panels=[
            UiPanelDeclaration(
                id=f"{plugin_id}-panel",
                title="Test Panel",
                route_segment="panel",
                placement="sidebar",
                icon="Puzzle",
                required_permission=f"{plugin_id}.read"
            )
        ]
    )


@pytest.mark.asyncio
async def test_plugin_loader_registers_and_seeds(db_session: AsyncSession):
    global on_load_called, on_unload_called
    on_load_called = False
    on_unload_called = False

    session_factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    test_app = FastAPI()
    loader = PluginLoader(test_app, session_factory)

    manifest = make_test_manifest("unit_test_plugin")

    # 1. Load the plugin
    await loader.load_plugin(manifest)

    # Assert database records
    result = await db_session.execute(select(PluginRegistry).where(PluginRegistry.id == "unit_test_plugin"))
    db_plugin = result.scalar_one_or_none()
    assert db_plugin is not None
    assert db_plugin.name == "Test Dynamic Plugin"
    assert db_plugin.is_enabled is True

    perm_result = await db_session.execute(select(Permission).where(Permission.key == "unit_test_plugin.read"))
    db_perm = perm_result.scalar_one_or_none()
    assert db_perm is not None
    assert db_perm.plugin_id == "unit_test_plugin"

    # Assert lifecycle hooks were executed and stored
    assert on_load_called is True
    assert "unit_test_plugin" in loader.loaded_plugins

    # 2. Unload the plugin
    await loader.unload_all()
    assert on_unload_called is True
    assert len(loader.loaded_plugins) == 0


@pytest.mark.asyncio
async def test_plugin_loader_disabled_skip(db_session: AsyncSession):
    global on_load_called
    on_load_called = False

    # Insert a disabled record in the database first
    disabled_plugin = PluginRegistry(
        id="disabled_test_plugin",
        name="Disabled Plugin",
        version="1.0.0",
        is_enabled=False,
        config={}
    )
    db_session.add(disabled_plugin)
    await db_session.commit()

    session_factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    test_app = FastAPI()
    loader = PluginLoader(test_app, session_factory)

    manifest = make_test_manifest("disabled_test_plugin")

    # Load should update info, but NOT run hooks or mount routes because it is disabled
    await loader.load_plugin(manifest)

    # Force SQLAlchemy to discard cached object and fetch from DB
    db_session.expire_all()

    # Check that update happened
    result = await db_session.execute(select(PluginRegistry).where(PluginRegistry.id == "disabled_test_plugin"))
    db_plugin = result.scalar_one()
    assert db_plugin.name == "Test Dynamic Plugin"
    assert db_plugin.is_enabled is False

    # Check hooks were not executed
    assert on_load_called is False
    assert "disabled_test_plugin" not in loader.loaded_plugins


@pytest.mark.asyncio
async def test_active_plugins_and_sample_router_endpoints(db_session: AsyncSession, super_admin: User):
    # Ensure the sample plugin workspace is loaded in the actual app for endpoint testing.
    # The actual app runs the PluginLoader inside lifespan against the real plugins dir.
    # In tests, override_db provides the isolated DB session.
    # Let's seed a sample plugin registry record so that the loader enables it.
    session_factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    
    # Run the real app's loader manually to mount routes on the test app instance.
    loader = PluginLoader(app, session_factory)
    manifest = make_test_manifest("endpoint_test_plugin")
    await loader.load_plugin(manifest)
    
    # Store our mock loader in app.state.plugin_loader so the endpoint can read from it
    app.state.plugin_loader = loader

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Test GET /api/plugins/active (authenticated)
        response = await request_as(ac, super_admin.id, "GET", "/api/plugins/active")
        assert response.status_code == 200
        active_plugins = response.json()
        assert len(active_plugins) >= 1
        
        # Verify schema elements
        plugin_entry = next((p for p in active_plugins if p["id"] == "endpoint_test_plugin"), None)
        assert plugin_entry is not None
        assert plugin_entry["name"] == "Test Dynamic Plugin"
        assert len(plugin_entry["ui_panels"]) == 1
        assert plugin_entry["ui_panels"][0]["route_segment"] == "panel"
        assert plugin_entry["ui_panels"][0]["icon"] == "Puzzle"

        # 2. Test dynamic router mounting under /api/plugins/{plugin_id}
        response = await request_as(ac, super_admin.id, "GET", "/api/plugins/endpoint_test_plugin/test-endpoint")
        assert response.status_code == 200
        assert response.json() == {"message": "Success"}
