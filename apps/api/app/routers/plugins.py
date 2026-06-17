"""Plugins router — plugin registry management."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.db.models import PluginRegistry
from app.dependencies import DbSession
from app.schemas.plugins import PluginOut, PluginUpdate

router = APIRouter(prefix="/api/plugins", tags=["plugins"])


@router.get("/", response_model=list[PluginOut])
async def list_plugins(db: DbSession) -> list[PluginRegistry]:
    result = await db.execute(select(PluginRegistry).order_by(PluginRegistry.name))
    return list(result.scalars().all())


@router.get("/{plugin_id}", response_model=PluginOut)
async def get_plugin(plugin_id: str, db: DbSession) -> PluginRegistry:
    plugin = await db.get(PluginRegistry, plugin_id)
    if not plugin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found.")
    return plugin


@router.patch("/{plugin_id}", response_model=PluginOut)
async def update_plugin(plugin_id: str, payload: PluginUpdate, db: DbSession) -> PluginRegistry:
    plugin = await db.get(PluginRegistry, plugin_id)
    if not plugin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(plugin, field, value)
    await db.commit()
    await db.refresh(plugin)
    return plugin
