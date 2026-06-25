"""Pydantic v2 schemas for PluginRegistry endpoints."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class PluginOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    version: str
    description: str | None
    is_enabled: bool
    config: dict[str, Any]
    installed_at: datetime
    updated_at: datetime


class PluginUpdate(BaseModel):
    is_enabled: bool | None = None
    config: dict[str, Any] | None = None


class UiPanelOut(BaseModel):
    id: str
    title: str
    route_segment: str
    placement: str
    required_permission: str | None = None
    icon: str


class ActivePluginOut(BaseModel):
    id: str
    name: str
    version: str
    description: str | None = None
    ui_panels: list[UiPanelOut] = []

