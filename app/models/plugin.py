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

    # Foreign key to user
    user_id: int = Field(foreign_key="user.id", index=True)

    # Plugin name (must match plugin identifier)
    plugin_name: str = Field(max_length=255, index=True)

    # Whether the plugin is enabled for this user
    enabled: bool = Field(default=True)

    # User-specific configuration for this plugin (JSON)
    # This allows each user to have different settings for the same plugin
    # Example: {"api_key": "user-specific-key", "theme": "dark"}
    config: dict = Field(default={}, sa_column=Column(JSON))

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
