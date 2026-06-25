"""
FastAPI application entry point.

Lifespan:
  - Runs Alembic migrations on startup (upgrade to head).
  - Seeds system groups, permissions, role mappings, and forks.
  - Starts the EventBus (connects to Redis if configured).
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import get_engine, get_sessionmaker
from app.db.seeder import run_seeds
from app.events import event_bus

logger = logging.getLogger(__name__)

# Env vars the Alembic env.py needs access to — pydantic-settings reads from
# .env but does NOT export to os.environ, so we propagate them here so that
# code that reads os.environ (Alembic) can find them.
_ALEMBIC_ENV_VARS = ("DATABASE_URL",)


def _ensure_alembic_env(settings) -> None:
    for key in _ALEMBIC_ENV_VARS:
        val = getattr(settings, key.lower(), None) or getattr(settings, key, None)
        if val is not None and key not in os.environ:
            os.environ[key] = str(val)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Application startup / shutdown lifecycle."""
    settings = get_settings()

    # Ensure Alembic can discover DATABASE_URL from the environment
    _ensure_alembic_env(settings)

    # Run Alembic migrations programmatically
    logger.info("Running Alembic migrations…")
    import asyncio
    from alembic import command
    from alembic.config import Config as AlembicConfig

    def _run_migrations() -> None:
        alembic_cfg = AlembicConfig("alembic.ini")
        alembic_cfg.set_main_option("skip_logging_config", "True")
        command.upgrade(alembic_cfg, "head")

    await asyncio.to_thread(_run_migrations)
    logger.info("Migrations complete.")

    # Seed reference data
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        await run_seeds(session)

    # Start the event bus so that plugins can publish/subscribe during on_load
    await event_bus.start(settings.redis_url)

    # Initialize and run dynamic PluginLoader
    from app.plugin_sdk.loader import PluginLoader
    plugin_loader = PluginLoader(application, session_factory)
    application.state.plugin_loader = plugin_loader
    await plugin_loader.discover_and_load()

    # Start periodic Discord sync scheduler if enabled
    if settings.enable_sync_scheduler:
        from app.provisioning.scheduler import start_scheduler
        await start_scheduler(
            interval_minutes=settings.sync_interval_minutes,
            guild_id=settings.discord_guild_id,
            bot_token=settings.discord_bot_token,
        )

    logger.info("bnb-api is ready.")
    yield

    # Shutdown lifecycle
    # Stop sync scheduler if enabled
    if settings.enable_sync_scheduler:
        from app.provisioning.scheduler import stop_scheduler
        await stop_scheduler()

    # Unload plugins and trigger their on_unload hooks BEFORE stopping event_bus
    if hasattr(application.state, "plugin_loader"):
        await application.state.plugin_loader.unload_all()

    # Stop the event bus after plugins have unloaded
    await event_bus.stop()

    # Dispose the engine connection pool
    await get_engine().dispose()
    logger.info("bnb-api shut down cleanly.")



def create_app() -> FastAPI:
    settings = get_settings()

    application = FastAPI(
        title="bnb-motherboard API",
        version="0.1.1",
        description="Internal operations platform for the bits&bytes network.",
        lifespan=lifespan,
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    # CORS — tighten in production via settings
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    from app.routers import auth, health, users, groups, forks, audit, sync, plugins, finance, iam, admin
    application.include_router(auth.router)
    application.include_router(health.router)
    application.include_router(users.router)
    application.include_router(groups.router)
    application.include_router(forks.router)
    application.include_router(audit.router)
    application.include_router(sync.router)
    application.include_router(plugins.router)
    application.include_router(finance.router)
    application.include_router(iam.router, prefix="/api/iam", tags=["iam"])
    application.include_router(admin.router)

    return application


app = create_app()
