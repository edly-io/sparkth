"""
Plugin models for plugin registry and user-level plugin preferences.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlmodel import JSON, Column, Field, Relationship

from app.models.base import SoftDeleteModel, TimestampedModel


class Plugin(TimestampedModel, SoftDeleteModel, table=True):
    __tablename__ = "plugins"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=255, unique=True, index=True)
    enabled: bool = Field(default=True)

    user_plugins: list["UserPlugin"] = Relationship(back_populates="plugin")


class UserPlugin(TimestampedModel, SoftDeleteModel, table=True):
    __tablename__ = "user_plugins"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    plugin_id: int = Field(foreign_key="plugins.id", index=True)
    enabled: bool = Field(default=True)
    config: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    plugin: "Plugin" = Relationship(back_populates="user_plugins")
