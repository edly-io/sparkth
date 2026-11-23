"""Request models for the plugin preference endpoints."""

from typing import Any

from pydantic import BaseModel


class UpdatePluginRequest(BaseModel):
    """Request model for turning a plugin on or off for the calling user."""

    enabled: bool


class PluginConfigRequest(BaseModel):
    """Request model for updating the calling user's plugin configuration."""

    config: dict[str, Any]
