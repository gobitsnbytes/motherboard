"""Health check and system status router."""

import logging
import httpx
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.config import get_settings
from app.dependencies import DbDep, CurrentUserDep
from app.events import event_bus
from app.db.models import SyncRun

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Basic process liveness check."""
    return {"status": "ok"}


@router.get("/health/ready")
async def health_ready(db: DbDep) -> dict[str, str]:
    """Readiness check that verifies database and redis connectivity."""
    db_ok = False
    try:
        await db.execute(select(1))
        db_ok = True
    except Exception as e:
        logger.error("Database readiness check failed: %s", e)

    redis_ok = True
    try:
        if event_bus.redis:
            await event_bus.redis.ping()
    except Exception as e:
        logger.error("Redis readiness check failed: %s", e)
        redis_ok = False

    if not db_ok or not redis_ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "degraded",
                "database": "healthy" if db_ok else "unhealthy",
                "redis": "healthy" if redis_ok else "unhealthy",
            },
        )

    return {
        "status": "ok",
        "database": "healthy",
        "redis": "healthy",
    }


@router.get("/api/health/status")
async def get_detailed_status(db: DbDep, current_user: CurrentUserDep) -> dict[str, Any]:
    """Return detailed health and status information for dashboard widgets."""
    # Database check
    db_status = "healthy"
    try:
        await db.execute(select(1))
    except Exception:
        db_status = "unhealthy"

    # Redis check
    redis_status = "healthy"
    if not event_bus.redis:
        redis_status = "unconfigured"
    else:
        try:
            await event_bus.redis.ping()
        except Exception:
            redis_status = "unhealthy"

    # Discord check
    settings = get_settings()
    discord_status = "connected"
    if not settings.discord_bot_token or not settings.discord_guild_id:
        discord_status = "unconfigured"
    else:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                headers = {"Authorization": f"Bot {settings.discord_bot_token}"}
                resp = await client.get("https://discord.com/api/v10/users/@me", headers=headers)
                if resp.status_code != 200:
                    discord_status = f"error_{resp.status_code}"
        except Exception:
            discord_status = "disconnected"

    # Last Sync check
    sync_status = "unknown"
    last_sync_time = None
    try:
        res = await db.execute(select(SyncRun).order_by(SyncRun.started_at.desc()).limit(1))
        last_run = res.scalar_one_or_none()
        if last_run:
            last_sync_time = last_run.started_at.isoformat()
            if last_run.status == "failed" or (last_run.errors and len(last_run.errors) > 0):
                sync_status = "unhealthy"
            elif last_run.status == "running":
                sync_status = "syncing"
            else:
                sync_status = "healthy"
        else:
            sync_status = "no_runs"
    except Exception:
        pass

    return {
        "status": "ok",
        "database": db_status,
        "redis": redis_status,
        "discord": discord_status,
        "sync": sync_status,
        "last_sync_at": last_sync_time,
    }

