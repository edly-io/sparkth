"""
Plugin models for plugin registry and user-level plugin preferences.
"""

from typing import Optional

from sqlmodel import JSON, Column, Field

from app.models.base import SoftDeleteModel, TimestampedModel


class Plugin(TimestampedModel, SoftDeleteModel, table=True):
    """
    Central registry of plugins in the system.

    Simple table to track which plugins are available.
    Detailed metadata comes from plugins.json and loaded plugin instances.
    """

    __tablename__ = "plugins"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=255, unique=True, index=True)
    enabled: bool = Field(default=True)  # System-level enable/disable


class UserPlugin(TimestampedModel, SoftDeleteModel, table=True):
    """
    User-specific plugin preferences.

    Junction table linking users to plugins with individual settings.
    """

    __tablename__ = "user_plugins"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    plugin_id: int = Field(foreign_key="plugins.id", index=True)
    enabled: bool = Field(default=True)
    config: dict = Field(default={}, sa_column=Column(JSON))
