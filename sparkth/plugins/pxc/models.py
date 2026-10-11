"""The PXC plugin's table: one row per activity an author generated.

A row is written once, after a successful build. An update changes its title, description and
``placed_at``, never its id, so activity instances placed in courses keep launching the same
activity. The files live on disk in the activity's revision directories, behind
``generated_activity_dir(id)``; the row is what ties them to their owner.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime
from sqlmodel import Column, Field, SQLModel, Text
from uuid6 import uuid7

from sparkth.lib.models import utc_now


class PxcActivity(SQLModel, table=True):
    """One generated activity, owned by the author who built it."""

    __tablename__ = "pxc_activities"

    id: UUID = Field(default_factory=uuid7, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", index=True, nullable=False)
    title: str = Field(max_length=255, nullable=False)
    description: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(
        sa_type=DateTime(timezone=True),  # type: ignore
        default_factory=utc_now,
        nullable=False,
    )
    # Null until the activity is first placed in a course. Once set, an update may not remove or change a field.
    placed_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
        nullable=True,
    )
