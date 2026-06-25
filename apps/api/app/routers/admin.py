"""Admin actions router for settings and danger zone commands."""

import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SyncRun
from app.dependencies import DbDep, CurrentUserDep
from app.iam.policy import require_permission
from app.events import event_bus
from app.db.seeder import run_seeds

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/reset-cache", status_code=status.HTTP_200_OK)
async def reset_cache(
    db: DbDep,
    current_user: CurrentUserDep,
) -> dict[str, str]:
    """Flush the Redis cache database."""
    await require_permission(db, current_user, "admin.settings.write")
    
    if not event_bus.redis:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Redis cache is not configured or connected.",
        )
        
    try:
        await event_bus.redis.flushdb()
        logger.info("Redis cache cleared by admin user %s", current_user.user_id)
        return {"status": "ok", "message": "Cache database flushed successfully."}
    except Exception as e:
        logger.error("Failed to flush Redis cache: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to flush cache: {e}",
        )


@router.post("/rebuild-permissions", status_code=status.HTTP_200_OK)
async def rebuild_permissions(
    request: Request,
    db: DbDep,
    current_user: CurrentUserDep,
) -> dict[str, str]:
    """Rebuild all system permissions and group mappings from seed data."""
    await require_permission(db, current_user, "admin.settings.write")
    
    try:
        logger.info("Rebuilding permissions and seed data by admin user %s", current_user.user_id)
        await run_seeds(db)
        
        # Trigger plugin loader to discover/reload if present
        loader = getattr(request.app.state, "plugin_loader", None)
        if loader:
            await loader.discover_and_load()
            
        return {"status": "ok", "message": "Core and plugin permissions and role mappings rebuilt."}
    except Exception as e:
        logger.error("Failed to rebuild permissions: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rebuild permissions: {e}",
        )


@router.post("/clear-sync-state", status_code=status.HTTP_200_OK)
async def clear_sync_state(
    db: DbDep,
    current_user: CurrentUserDep,
) -> dict[str, str]:
    """Clear all records from the sync run history."""
    await require_permission(db, current_user, "admin.settings.write")
    
    try:
        logger.info("Clearing sync history by admin user %s", current_user.user_id)
        await db.execute(delete(SyncRun))
        await db.commit()
        return {"status": "ok", "message": "Sync run history cleared successfully."}
    except Exception as e:
        logger.error("Failed to clear sync state: %s", e)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear sync history: {e}",
        )
