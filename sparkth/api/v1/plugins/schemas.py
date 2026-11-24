"""Request and response models for the plugin preference and system-wide switch endpoints."""

from typing import Any

from pydantic import BaseModel


class UpdatePluginRequest(BaseModel):
    """Request model for turning a plugin on or off, for the calling user or for everyone."""

    enabled: bool


class PluginSystemStateResponse(BaseModel):
    """Response model for a plugin's system-wide switch."""

    plugin_name: str
    enabled: bool


class PluginConfigRequest(BaseModel):
    """Request model for updating the calling user's plugin configuration."""

    config: dict[str, Any]
