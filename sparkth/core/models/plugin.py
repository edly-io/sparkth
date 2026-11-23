"""
Plugin models for plugin registry and user-level plugin preferences.
"""

from typing import Any

from sqlalchemy import UniqueConstraint
from sqlmodel import JSON, Column, Field, Relationship

from sparkth.core.models.base import SoftDeleteModel, TimestampedModel
from sparkth.core.models.types import EncryptedJSON


class Plugin(TimestampedModel, SoftDeleteModel, table=True):
    """
    Central registry of plugins in the system.

    Simple table to track which plugins are available.
    Detailed metadata comes from plugins.json and loaded plugin instances.
    """

    __tablename__ = "plugins"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=255, unique=True, index=True)
    is_core: bool = Field(default=False)
    enabled: bool = Field(default=True)
    config_schema: dict[str, Any] = Field(default={}, sa_column=Column(JSON))

    user_preferences: list["UserPluginPreference"] = Relationship(back_populates="plugin")


class UserPluginPreference(TimestampedModel, SoftDeleteModel, table=True):
    """One user's preference for one plugin: whether they turned it on, and their saved configuration."""

    __tablename__ = "user_plugin_preferences"
    __table_args__ = (UniqueConstraint("user_id", "plugin_id", name="uq_user_plugin_preference"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    plugin_id: int = Field(foreign_key="plugins.id", index=True)
    enabled: bool = Field(default=True)
    config: dict[str, Any] = Field(default_factory=dict, sa_column=Column(EncryptedJSON))

    plugin: "Plugin" = Relationship(back_populates="user_preferences")
