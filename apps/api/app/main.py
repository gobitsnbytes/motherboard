"""
FastAPI application entry point.

Lifespan:
  - Runs Alembic migrations on startup (upgrade to head).
  - Seeds system groups, permissions, role mappings, and forks.
  - Starts the EventBus (connects to Redis if configured).
"""

import logging
import os
import asyncio
import re
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import sentry_sdk

from app.config import get_settings
from app.database import get_engine, get_sessionmaker
from app.db.seeder import run_seeds
from app.events import event_bus
from app.observability import (
    REQUEST_LOGGER,
    capture_background_exception,
    emit_runtime_log,
    init_sentry,
)

logger = logging.getLogger(__name__)
request_logger = logging.getLogger(REQUEST_LOGGER)
_calendar_reconciliation_task: asyncio.Task | None = None
_background_startup_task: asyncio.Task | None = None
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")

# Env vars the Alembic env.py needs access to — pydantic-settings reads from
# .env but does NOT export to os.environ, so we propagate them here so that
# code that reads os.environ (Alembic) can find them.
_ALEMBIC_ENV_VARS = ("DATABASE_URL",)


def _ensure_alembic_env(settings) -> None:
    for key in _ALEMBIC_ENV_VARS:
        val = getattr(settings, key.lower(), None) or getattr(settings, key, None)
        if val is not None and key not in os.environ:
            os.environ[key] = str(val)


async def _initialize_application_services(
    application, settings, session_factory
) -> None:
    """Initialize remote-backed services without blocking process liveness."""
    failures: list[str] = []

    try:
        async with session_factory() as session:
            await asyncio.wait_for(run_seeds(session), timeout=10)
    except Exception as exc:
        failures.append("database_seed")
        logger.warning("Database seed startup skipped: %s", exc)
        capture_background_exception(
            exc, subsystem="startup", operation="database_seed"
        )

    try:
        await asyncio.wait_for(event_bus.start(settings.redis_url), timeout=2)
    except Exception as exc:
        failures.append("event_bus")
        logger.warning("EventBus startup skipped: %s", exc)
        capture_background_exception(exc, subsystem="startup", operation="event_bus")

    try:
        from app.plugin_sdk.loader import PluginLoader

        plugin_loader = PluginLoader(application, session_factory)
        application.state.plugin_loader = plugin_loader
        await asyncio.wait_for(plugin_loader.discover_and_load(), timeout=5)
    except Exception as exc:
        failures.append("plugins")
        logger.warning("PluginLoader startup skipped: %s", exc)
        capture_background_exception(exc, subsystem="startup", operation="plugins")

    if settings.enable_sync_scheduler:
        try:
            from app.provisioning.scheduler import start_scheduler

            await start_scheduler(
                interval_minutes=settings.sync_interval_minutes,
                guild_id=settings.discord_guild_id,
                bot_token=settings.discord_bot_token,
            )
        except Exception as exc:
            failures.append("discord_scheduler")
            logger.warning("Discord scheduler startup skipped: %s", exc)
            capture_background_exception(
                exc, subsystem="startup", operation="discord_scheduler"
            )

    try:
        from app.services.legal_agent import start_legal_agent_jobs

        await start_legal_agent_jobs()
    except Exception as exc:
        failures.append("legal_agent")
        logger.warning("Legal Agent scheduler startup skipped: %s", exc)
        capture_background_exception(exc, subsystem="startup", operation="legal_agent")

    try:
        from app.routers.forms import start_form_cleanup

        await start_form_cleanup()
    except Exception as exc:
        failures.append("form_cleanup")
        logger.warning("Public form cleanup scheduler startup skipped: %s", exc)
        capture_background_exception(exc, subsystem="startup", operation="form_cleanup")

    async def _calendar_reconciliation_loop() -> None:
        from app.services.calendar_routing import reconcile_unknown_bookings

        while True:
            await asyncio.sleep(15 * 60)
            try:
                async with session_factory() as session:
                    repaired = await reconcile_unknown_bookings(session)
                if repaired:
                    logger.info("Reconciled %s uncertain Cal.com booking(s).", repaired)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Cal.com reconciliation failed (non-fatal): %s", exc)
                capture_background_exception(
                    exc, subsystem="calendar", operation="reconcile_unknown_bookings"
                )

    global _calendar_reconciliation_task
    _calendar_reconciliation_task = asyncio.create_task(_calendar_reconciliation_loop())
    application.state.startup_status = "degraded" if failures else "ready"
    application.state.startup_failures = failures
    logger.info(
        "Background startup finished with status=%s failures=%s",
        application.state.startup_status,
        failures,
    )


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Application startup / shutdown lifecycle."""
    global _background_startup_task, _calendar_reconciliation_task
    settings = get_settings()

    # Ensure Alembic can discover DATABASE_URL from the environment
    _ensure_alembic_env(settings)

    # Session factory for DB access
    session_factory = get_sessionmaker()

    application.state.startup_status = "starting"
    application.state.startup_failures = []
    _background_startup_task = asyncio.create_task(
        _initialize_application_services(application, settings, session_factory)
    )

    logger.info(
        "bnb-api is accepting requests; dependency startup continues in background."
    )
    yield

    # Shutdown lifecycle
    if _background_startup_task and not _background_startup_task.done():
        _background_startup_task.cancel()
        try:
            await _background_startup_task
        except asyncio.CancelledError:
            pass
    _background_startup_task = None
    # Stop sync scheduler if enabled
    if settings.enable_sync_scheduler:
        from app.provisioning.scheduler import stop_scheduler

        await stop_scheduler()

    # Stop Legal Agent scheduler
    try:
        from app.services.legal_agent import stop_legal_agent_jobs

        await stop_legal_agent_jobs()
    except Exception as legal_agent_stop_err:
        logger.warning(
            f"Legal Agent scheduler shutdown skipped: {legal_agent_stop_err}"
        )

    from app.routers.forms import stop_form_cleanup

    await stop_form_cleanup()

    if _calendar_reconciliation_task:
        _calendar_reconciliation_task.cancel()
        try:
            await _calendar_reconciliation_task
        except asyncio.CancelledError:
            pass
        _calendar_reconciliation_task = None

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
    init_sentry(settings)

    application = FastAPI(
        title="bnb-motherboard API",
        version=settings.app_version,
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

    @application.middleware("http")
    async def log_server_errors(request: Request, call_next):
        inbound_request_id = request.headers.get("x-request-id", "")
        request_id = (
            inbound_request_id
            if _REQUEST_ID_PATTERN.fullmatch(inbound_request_id)
            else uuid.uuid4().hex
        )
        sentry_sdk.get_isolation_scope().set_tag("request_id", request_id)
        started_at = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            route = getattr(request.scope.get("route"), "path", "unmatched")
            emit_runtime_log(
                "api.request.failed",
                method=request.method,
                route=route,
                status_code=500,
                request_id=request_id,
                duration_ms=round((time.perf_counter() - started_at) * 1000),
            )
            request_logger.exception(
                "request_failed method=%s path=%s request_id=%s duration_ms=%d",
                request.method,
                request.url.path,
                request_id,
                round((time.perf_counter() - started_at) * 1000),
            )
            raise
        response.headers["X-Request-ID"] = request_id
        route = getattr(request.scope.get("route"), "path", "unmatched")
        if not route.startswith(("/health", "/api/health")):
            emit_runtime_log(
                "api.request.failed"
                if response.status_code >= 500
                else "api.request.completed",
                method=request.method,
                route=route,
                status_code=response.status_code,
                request_id=request_id,
                duration_ms=round((time.perf_counter() - started_at) * 1000),
            )
        if response.status_code >= 500:
            request_logger.error(
                "request_failed method=%s path=%s status=%d request_id=%s duration_ms=%d",
                request.method,
                request.url.path,
                response.status_code,
                request_id,
                round((time.perf_counter() - started_at) * 1000),
            )
        return response

    # Include routers
    from app.routers import (
        auth,
        health,
        users,
        groups,
        forks,
        audit,
        sync,
        plugins,
        finance,
        iam,
        admin,
        meetings,
        calendar,
        dyslexic,
        cloud,
        signatures,
        contract_assistant,
        forms,
        onboarding,
        finance_ledger,
    )

    application.include_router(auth.router)
    application.include_router(health.router)
    application.include_router(users.router)
    application.include_router(groups.router)
    application.include_router(forks.router)
    application.include_router(audit.router)
    application.include_router(sync.router)
    application.include_router(plugins.router)
    application.include_router(finance.router)
    application.include_router(finance_ledger.router)
    application.include_router(iam.router, prefix="/api/iam", tags=["iam"])
    application.include_router(meetings.router)
    application.include_router(calendar.router)
    application.include_router(admin.router)
    application.include_router(dyslexic.router)
    application.include_router(cloud.router)
    application.include_router(signatures.router)
    application.include_router(contract_assistant.router)
    application.include_router(forms.router)
    application.include_router(onboarding.router)

    return application


app = create_app()
