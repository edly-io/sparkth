"""Request models for the user plugin endpoints."""

from typing import Any

from pydantic import BaseModel


class UpdateUserPluginRequest(BaseModel):
    """Request model for updating user plugin state."""

    enabled: bool


class UserPluginConfigRequest(BaseModel):
    """Request model for updating user plugin configuration."""

    config: dict[str, Any]
