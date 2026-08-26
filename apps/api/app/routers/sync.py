"""Sync router — Discord provisioning sync status and manual trigger."""

import uuid
from datetime import datetime, timezone
import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, status, BackgroundTasks, Query
from sqlalchemy import select

from app.config import get_settings
from app.db.models import SyncRun
from app.dependencies import DbDep, CurrentUserDep
from app.iam.policy import require_permission
from app.schemas.sync import SyncRunOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sync", tags=["sync"])


async def background_sync_task(run_id: uuid.UUID, bot_token: str, guild_id: str):
    """Executes the Discord sync in the background."""
    from app.database import get_sessionmaker
    from app.provisioning.client import DiscordClient
    from app.provisioning.sync import run_sync

    logger.info("Starting background manual sync task for run %s", run_id)
    session_factory = get_sessionmaker()
    discord_client = DiscordClient(bot_token)

    async with session_factory() as session:
        try:
            await run_sync(
                db=session,
                discord_client=discord_client,
                guild_id=guild_id,
                trigger="manual",
                existing_run_id=run_id,
            )
        except Exception as e:
            logger.error("Background manual sync task failed for run %s: %s", run_id, e)


@router.get("/runs", response_model=list[SyncRunOut])
async def list_sync_runs(
    db: DbDep,
    current_user: CurrentUserDep,
    limit: int = 20,
) -> list[SyncRun]:
    """List recent Discord sync runs."""
    await require_permission(db, current_user, "provisioning.sync.read")
    result = await db.execute(
        select(SyncRun).order_by(SyncRun.started_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


@router.get("/runs/{run_id}", response_model=SyncRunOut)
async def get_sync_run(
    run_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUserDep,
) -> SyncRun:
    """Retrieve details of a specific sync run."""
    await require_permission(db, current_user, "provisioning.sync.read")
    run = await db.get(SyncRun, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sync run not found.")
    return run


@router.post("/trigger", response_model=SyncRunOut, status_code=status.HTTP_202_ACCEPTED)
async def trigger_sync(
    db: DbDep,
    current_user: CurrentUserDep,
    background_tasks: BackgroundTasks,
) -> SyncRun:
    """
    Enqueue a manual Discord member sync.
    Runs the sync engine asynchronously in a FastAPI background task.
    """
    await require_permission(db, current_user, "provisioning.sync.trigger")

    settings = get_settings()
    if not settings.discord_bot_token or not settings.discord_guild_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Discord bot settings (token or guild_id) are not configured.",
        )

    run = SyncRun(
        trigger="manual",
        status="running",
        started_at=datetime.now(timezone.utc),
        errors=[],
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    background_tasks.add_task(
        background_sync_task,
        run.id,
        settings.discord_bot_token,
        settings.discord_guild_id,
    )

    return run


@router.post("/notion")
async def trigger_notion_sync(
    db: DbDep,
    current_user: CurrentUserDep,
):
    """
    Synchronize real forks and team members from Notion databases into motherboard.
    Forks sync from the Fork Registry; team members sync when NOTION_TEAM_DB is configured.
    """
    await require_permission(db, current_user, "provisioning.sync.trigger")
    from app.provisioning.notion_sync import sync_forks_from_notion, sync_team_from_notion
    fork_result = await sync_forks_from_notion(db)
    team_result = await sync_team_from_notion(db)
    return {"forks": fork_result, "team": team_result}
