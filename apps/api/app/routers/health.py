"""Health check and system status router."""

import asyncio
import logging
import os
from collections.abc import Awaitable
from typing import Any, TypeVar

import httpx

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select, func

from app.config import get_settings
from app.dependencies import DbDep, OptionalUserDep
from app.events import event_bus
from app.db.models import SyncRun, Group, Permission, DiscordRoleMapping

logger = logging.getLogger(__name__)
T = TypeVar("T")

DB_TIMEOUT_SECONDS = 0.75
REDIS_TIMEOUT_SECONDS = 0.25
DISCORD_TIMEOUT_SECONDS = 0.75


async def _within(awaitable: Awaitable[T], timeout: float) -> T:
    """Bound an optional health probe so one dependency cannot stall the page."""
    return await asyncio.wait_for(awaitable, timeout=timeout)


router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Basic process liveness check."""
    return {"status": "ok"}


@router.get("/health/ready")
async def health_ready(request: Request, db: DbDep) -> dict[str, str]:
    """Readiness check that verifies database and redis connectivity."""
    db_ok = False
    try:
        await _within(db.execute(select(1)), DB_TIMEOUT_SECONDS)
        db_ok = True
    except Exception as e:
        logger.error("Database readiness check failed: %s", e)

    redis_ok = True
    try:
        if event_bus.redis:
            await _within(event_bus.redis.ping(), REDIS_TIMEOUT_SECONDS)
    except Exception as e:
        logger.error("Redis readiness check failed: %s", e)
        redis_ok = False

    startup_status = getattr(request.app.state, "startup_status", "ready")
    if not db_ok or not redis_ok or startup_status == "starting":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "degraded",
                "database": "healthy" if db_ok else "unhealthy",
                "redis": "healthy" if redis_ok else "unhealthy",
                "startup": startup_status,
            },
        )

    return {
        "status": "ok",
        "database": "healthy",
        "redis": "healthy",
        "startup": startup_status,
    }


@router.get("/api/health/status")
async def get_detailed_status(
    db: DbDep, current_user: OptionalUserDep = None
) -> dict[str, Any]:
    """Return detailed health and status information for dashboard widgets."""
    # Database check
    db_status = "healthy"
    try:
        await _within(db.execute(select(1)), DB_TIMEOUT_SECONDS)
    except Exception as exc:
        logger.warning("Detailed health database probe failed: %s", exc)
        db_status = "unhealthy"

    # Redis check
    redis_status = "healthy"
    if not event_bus.redis:
        redis_status = "unconfigured"
    else:
        try:
            await _within(event_bus.redis.ping(), REDIS_TIMEOUT_SECONDS)
        except Exception as exc:
            logger.warning("Detailed health Redis probe failed: %s", exc)
            redis_status = "unhealthy"

    # Discord check
    settings = get_settings()
    discord_status = "connected"
    if not settings.discord_bot_token or not settings.discord_guild_id:
        discord_status = "unconfigured"
    else:
        try:
            async with httpx.AsyncClient(timeout=DISCORD_TIMEOUT_SECONDS) as client:
                headers = {"Authorization": f"Bot {settings.discord_bot_token}"}
                resp = await _within(
                    client.get(
                        "https://discord.com/api/v10/users/@me", headers=headers
                    ),
                    DISCORD_TIMEOUT_SECONDS,
                )
                if resp.status_code != 200:
                    discord_status = f"error_{resp.status_code}"
        except Exception as exc:
            logger.warning("Detailed health Discord probe failed: %s", exc)
            discord_status = "disconnected"

    # Last Sync check
    sync_status = "unknown"
    last_sync_time = None
    try:
        if db_status != "healthy":
            raise RuntimeError("database probe failed")
        res = await _within(
            db.execute(select(SyncRun).order_by(SyncRun.started_at.desc()).limit(1)),
            DB_TIMEOUT_SECONDS,
        )
        last_run = res.scalar_one_or_none()
        if last_run:
            last_sync_time = last_run.started_at.isoformat()
            if last_run.status == "failed" or (
                last_run.errors and len(last_run.errors) > 0
            ):
                sync_status = "unhealthy"
            elif last_run.status == "running":
                sync_status = "syncing"
            else:
                sync_status = "healthy"
        else:
            sync_status = "no_runs"
    except Exception as exc:
        logger.warning("Detailed health sync probe failed: %s", exc)

    env_name = os.environ.get("APP_ENV") or os.environ.get("NODE_ENV") or "development"
    app_version = settings.app_version

    groups_count = 0
    permissions_count = 0
    role_mappings_count = 0
    try:
        if db_status != "healthy":
            raise RuntimeError("database probe failed")
        groups_count = (
            await _within(
                db.scalar(select(func.count()).select_from(Group)), DB_TIMEOUT_SECONDS
            )
            or 0
        )
        permissions_count = (
            await _within(
                db.scalar(select(func.count()).select_from(Permission)),
                DB_TIMEOUT_SECONDS,
            )
            or 0
        )
        role_mappings_count = (
            await _within(
                db.scalar(select(func.count()).select_from(DiscordRoleMapping)),
                DB_TIMEOUT_SECONDS,
            )
            or 0
        )
    except Exception as e:
        logger.error("Failed to query counts for health status: %s", e)

    return {
        "status": (
            "ok"
            if db_status == "healthy"
            and redis_status in {"healthy", "unconfigured"}
            and discord_status in {"connected", "unconfigured"}
            else "degraded"
        ),
        "database": db_status,
        "redis": redis_status,
        "discord": discord_status,
        "sync": sync_status,
        "last_sync_at": last_sync_time,
        "version": app_version,
        "environment": env_name,
        "groups_count": groups_count,
        "permissions_count": permissions_count,
        "role_mappings_count": role_mappings_count,
    }
