from typing import Annotated, Any, Callable, Coroutine, Dict, List, Literal, Optional
from fastapi import APIRouter, FastAPI
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

Slug = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")]


class PluginContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    plugin_id: str
    db_session: AsyncSession
    # Core system wrapper functions
    audit: Callable[[str, str, str, Dict[str, Any]], Coroutine[Any, Any, None]]
    publish_event: Callable[[str, Dict[str, Any]], Coroutine[Any, Any, None]]


class PermissionDeclaration(BaseModel):
    key: str
    description: str


class UiPanelDeclaration(BaseModel):
    id: Slug
    title: str
    route_segment: Slug
    placement: Literal["sidebar", "modal", "embedded"]
    required_permission: Optional[str] = None
    icon: str


class PluginManifest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: Slug
    name: str
    version: str
    description: Optional[str] = None
    # Router instance to mount under /api/plugins/<plugin_id>
    router: Optional[APIRouter] = None
    # Lifecycle hooks
    on_load: Optional[Callable[[FastAPI, PluginContext], Coroutine[Any, Any, None]]] = None
    on_unload: Optional[Callable[[PluginContext], Coroutine[Any, Any, None]]] = None
    # Declarations
    permissions: List[PermissionDeclaration] = []
    ui_panels: List[UiPanelDeclaration] = []
