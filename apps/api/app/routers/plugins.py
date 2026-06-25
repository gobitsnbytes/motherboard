"""Plugins router — plugin registry management."""

from typing import Any
from fastapi import APIRouter, HTTPException, status, Request
from sqlalchemy import select

from app.db.models import PluginRegistry
from app.dependencies import CurrentUserDep, DbSession
from app.iam.policy import require_permission
from app.schemas.plugins import PluginOut, PluginUpdate, ActivePluginOut


router = APIRouter(prefix="/api/plugins", tags=["plugins"])


@router.get("/", response_model=list[PluginOut])
async def list_plugins(db: DbSession, current_user: CurrentUserDep) -> list[PluginRegistry]:
    await require_permission(db, current_user, "plugins.read")
    result = await db.execute(select(PluginRegistry).order_by(PluginRegistry.name))
    return list(result.scalars().all())


@router.get("/active", response_model=list[ActivePluginOut])
async def get_active_plugins(
    request: Request,
    db: DbSession,
    current_user: CurrentUserDep,
) -> list[dict[str, Any]]:
    """Return all currently loaded active plugins and their UI panel declarations."""
    await require_permission(db, current_user, "plugins.read")
    loader = getattr(request.app.state, "plugin_loader", None)
    if not loader:
        return []

    active_manifests = []
    for manifest in loader.loaded_plugins.values():
        active_manifests.append({
            "id": manifest.id,
            "name": manifest.name,
            "version": manifest.version,
            "description": manifest.description,
            "ui_panels": [
                {
                    "id": p.id,
                    "title": p.title,
                    "route_segment": p.route_segment,
                    "placement": p.placement,
                    "required_permission": p.required_permission,
                    "icon": p.icon,
                }
                for p in manifest.ui_panels
            ],
        })
    return active_manifests


@router.get("/{plugin_id}", response_model=PluginOut)
async def get_plugin(
    plugin_id: str,
    db: DbSession,
    current_user: CurrentUserDep,
) -> PluginRegistry:
    await require_permission(db, current_user, "plugins.read")
    plugin = await db.get(PluginRegistry, plugin_id)
    if not plugin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found.")
    return plugin


@router.patch("/{plugin_id}", response_model=PluginOut)
async def update_plugin(
    plugin_id: str,
    payload: PluginUpdate,
    db: DbSession,
    current_user: CurrentUserDep,
) -> PluginRegistry:
    await require_permission(db, current_user, "plugins.write")
    plugin = await db.get(PluginRegistry, plugin_id)
    if not plugin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(plugin, field, value)
    await db.commit()
    await db.refresh(plugin)
    return plugin
