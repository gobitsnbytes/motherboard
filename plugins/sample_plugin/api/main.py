import logging
from fastapi import APIRouter
from app.plugin_sdk.types import (
    PluginManifest,
    PermissionDeclaration,
    UiPanelDeclaration,
    PluginContext,
)

logger = logging.getLogger("sample_plugin")
router = APIRouter()


@router.get("/hello")
async def hello():
    """Sample API endpoint provided by the plugin."""
    return {"message": "Hello from the dynamic Sample Plugin!"}


async def on_load(app, ctx: PluginContext):
    """Executes on startup when the plugin is loaded."""
    logger.info(f"Sample plugin {ctx.plugin_id} on_load hook executing...")
    await ctx.audit(
        action="load",
        target_type="plugin",
        target_id=ctx.plugin_id,
        meta={"event": "plugin_mounted_and_loaded"}
    )
    await ctx.publish_event("plugin.loaded", {"plugin_id": ctx.plugin_id})


async def on_unload(ctx: PluginContext):
    """Executes on shutdown when the plugin is unloaded."""
    logger.info(f"Sample plugin {ctx.plugin_id} on_unload hook executing...")
    await ctx.audit(
        action="unload",
        target_type="plugin",
        target_id=ctx.plugin_id,
        meta={"event": "plugin_unmounted_and_unloaded"}
    )


def get_manifest() -> PluginManifest:
    """Returns the plugin manifest conforming to the Plugin SDK specification."""
    return PluginManifest(
        id="sample_plugin",
        name="Sample Plugin",
        version="0.1.0",
        description="A dynamic sample plugin demonstrating the motherboard Plugin SDK capabilities.",
        router=router,
        on_load=on_load,
        on_unload=on_unload,
        permissions=[
            PermissionDeclaration(key="sample.read", description="Permission to view sample plugin panels."),
            PermissionDeclaration(key="sample.write", description="Permission to modify sample plugin settings."),
        ],
        ui_panels=[
            UiPanelDeclaration(
                id="sample-plugin-panel",
                title="Sample Plugin",
                route_segment="sample",
                placement="sidebar",
                icon="Puzzle",
                required_permission="sample.read"
            )
        ]
    )
