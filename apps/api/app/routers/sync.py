"""Sync router — Discord provisioning sync status and manual trigger."""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.db.models import SyncRun
from app.dependencies import DbSession
from app.schemas.sync import SyncRunOut

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.get("/runs", response_model=list[SyncRunOut])
async def list_sync_runs(
    db: DbSession,
    limit: Annotated[int, ...] = 20,
) -> list[SyncRun]:
    result = await db.execute(
        select(SyncRun).order_by(SyncRun.started_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


@router.get("/runs/{run_id}", response_model=SyncRunOut)
async def get_sync_run(run_id: Annotated[uuid.UUID, ...], db: DbSession) -> SyncRun:
    run = await db.get(SyncRun, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sync run not found.")
    return run


@router.post("/trigger", response_model=SyncRunOut, status_code=status.HTTP_202_ACCEPTED)
async def trigger_sync(db: DbSession) -> SyncRun:
    """
    Enqueue a manual Discord member sync.
    The actual sync logic runs in the provisioning background worker;
    this endpoint creates the SyncRun record and signals the worker.
    """
    run = SyncRun(trigger="manual", status="running")
    db.add(run)
    await db.commit()
    await db.refresh(run)
    # TODO: emit 'provisioning.sync.triggered' event via EventBus (Phase 3)
    return run
