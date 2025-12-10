"""
Plugin models for user-level plugin preferences and configurations.
"""
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel, Column, JSON

from app.models.base import TimestampedModel, SoftDeleteModel


class UserPlugin(TimestampedModel, SoftDeleteModel, table=True):
    """
    User plugin preferences and configurations.

    This model stores which plugins are enabled/disabled for each user,
    plus any user-specific configuration for those plugins.
    """
    __tablename__ = "user_plugins"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    plugin_name: str = Field(max_length=255, index=True)
    enabled: bool = Field(default=True)

    # User-specific configuration for this plugin (JSON)
    config: dict = Field(default={}, sa_column=Column(JSON))
