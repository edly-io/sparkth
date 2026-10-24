import uuid
from typing import Any

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field

from .base import TimestampedModel


class AnalyticsView(TimestampedModel, table=True):
    """A saved Explore configuration, private to its owner."""

    __tablename__ = "analytics_view"
    __table_args__ = (UniqueConstraint("owner_id", "name"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: int = Field(foreign_key="user.id", ondelete="CASCADE", index=True)
    name: str = Field(max_length=100)
    # An Explore config without the period.
    config: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
