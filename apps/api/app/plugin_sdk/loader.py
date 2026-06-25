import importlib.util
import logging
import sys
import uuid
from pathlib import Path
from typing import Dict, Any
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from app.db.models import PluginRegistry, Permission
from app.plugin_sdk.types import PluginManifest, PluginContext

logger = logging.getLogger("plugin_loader")


class PluginLoader:
    def __init__(self, app: FastAPI, session_factory: async_sessionmaker, plugins_dir: Path | None = None):
        self.app = app
        self.session_factory = session_factory
        # If no plugins directory is provided, resolve it dynamically relative to this file
        self.plugins_dir = plugins_dir or (Path(__file__).resolve().parents[4] / "plugins")
        self.loaded_plugins: Dict[str, PluginManifest] = {}

    async def discover_and_load(self):
        """Scan the plugins folder, dynamically load main.py modules, register them, and mount them if enabled."""
        if not self.plugins_dir.exists():
            logger.warning(f"Plugins directory not found at: {self.plugins_dir}")
            return

        logger.info(f"Scanning plugins directory: {self.plugins_dir}")
        for p_dir in self.plugins_dir.iterdir():
            if not p_dir.is_dir():
                continue

            api_path = p_dir / "api"
            if not api_path.exists():
                continue

            api_main_path = api_path / "main.py"
            if not api_main_path.exists():
                continue

            logger.info(f"Discovered plugin candidate in: {p_dir.name}")
            try:
                # Load module dynamically with a unique namespace key to prevent caching collisions
                module_name = f"plugin_{p_dir.name}"
                spec = importlib.util.spec_from_file_location(module_name, api_main_path)
                if spec is None or spec.loader is None:
                    logger.error(f"Could not create import spec for plugin main.py in: {p_dir.name}")
                    continue

                plugin_module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = plugin_module
                spec.loader.exec_module(plugin_module)

                if not hasattr(plugin_module, "get_manifest"):
                    logger.error(f"Plugin {p_dir.name} does not export a 'get_manifest()' function.")
                    continue

                manifest: PluginManifest = plugin_module.get_manifest()
                await self.load_plugin(manifest)
            except Exception as e:
                logger.exception(f"Failed to dynamically load plugin {p_dir.name}: {e}")

    async def load_plugin(self, manifest: PluginManifest):
        """Idempotently register a plugin in the database and mount its router/lifespan hooks if enabled."""
        logger.info(f"Registering plugin: {manifest.id} (v{manifest.version})")
        
        async with self.session_factory() as session:
            # 1. Register or update the plugin registry entry
            result = await session.execute(select(PluginRegistry).where(PluginRegistry.id == manifest.id))
            db_plugin = result.scalar_one_or_none()

            if not db_plugin:
                db_plugin = PluginRegistry(
                    id=manifest.id,
                    name=manifest.name,
                    version=manifest.version,
                    description=manifest.description,
                    is_enabled=True,
                    config={}
                )
                session.add(db_plugin)
            else:
                db_plugin.name = manifest.name
                db_plugin.version = manifest.version
                db_plugin.description = manifest.description

            # 2. Seed/upsert permissions declared by this plugin
            for perm in manifest.permissions:
                perm_result = await session.execute(select(Permission).where(Permission.key == perm.key))
                db_perm = perm_result.scalar_one_or_none()

                if not db_perm:
                    db_perm = Permission(
                        id=uuid.uuid4(),
                        key=perm.key,
                        description=perm.description,
                        plugin_id=manifest.id
                    )
                    session.add(db_perm)
                else:
                    db_perm.description = perm.description
                    db_perm.plugin_id = manifest.id

            await session.commit()
            is_enabled = db_plugin.is_enabled

        # 3. Mount routes and call startup hooks if enabled
        if is_enabled:
            logger.info(f"Plugin {manifest.id} is enabled. Running on_load and mounting router...")
            if manifest.on_load:
                # Open a new session for the on_load context
                async with self.session_factory() as session:
                    ctx = PluginContext(
                        plugin_id=manifest.id,
                        db_session=session,
                        audit=self._make_audit_fn(manifest.id, session),
                        publish_event=self._make_publish_fn()
                    )
                    try:
                        await manifest.on_load(self.app, ctx)
                        await session.commit()
                    except Exception as e:
                        logger.exception(f"Error executing on_load for plugin {manifest.id}: {e}")
                        await session.rollback()
                        return

            if manifest.router:
                from fastapi import Depends
                from app.dependencies import get_current_user
                self.app.include_router(
                    manifest.router,
                    prefix=f"/api/plugins/{manifest.id}",
                    tags=[f"plugin:{manifest.id}"],
                    dependencies=[Depends(get_current_user)]
                )

            self.loaded_plugins[manifest.id] = manifest
            logger.info(f"Plugin {manifest.id} loaded successfully.")
        else:
            logger.info(f"Plugin {manifest.id} is disabled in the database. Skipping mount.")

    async def unload_all(self):
        """Execute on_unload hooks for all currently loaded plugins on application shutdown."""
        logger.info("Unloading all plugins...")
        for plugin_id, manifest in list(self.loaded_plugins.items()):
            if manifest.on_unload:
                logger.info(f"Running on_unload for plugin: {plugin_id}")
                async with self.session_factory() as session:
                    ctx = PluginContext(
                        plugin_id=manifest.id,
                        db_session=session,
                        audit=self._make_audit_fn(manifest.id, session),
                        publish_event=self._make_publish_fn()
                    )
                    try:
                        await manifest.on_unload(ctx)
                        await session.commit()
                    except Exception as e:
                        logger.exception(f"Error executing on_unload for plugin {plugin_id}: {e}")
                        await session.rollback()
        self.loaded_plugins.clear()

    def _make_audit_fn(self, plugin_id: str, session: AsyncSession):
        from app.iam.audit import write_audit_entry
        async def audit_fn(action: str, target_type: str, target_id: str, meta: Dict[str, Any]):
            await write_audit_entry(
                session,
                actor_id=None,
                action=f"plugin.{plugin_id}.{action}",
                target_type=target_type,
                target_id=target_id,
                metadata=meta
            )
        return audit_fn

    def _make_publish_fn(self):
        from app.events.bus import event_bus
        async def publish_fn(event_type: str, payload: Dict[str, Any]):
            await event_bus.publish(event_type, payload)
        return publish_fn
