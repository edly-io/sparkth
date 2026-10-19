"""The PXC plugin's tables: one row per activity an author generated, and its preview's recent failed actions.

A row is written once, after a successful build. Placement sets ``placed_at`` once, and an update
changes the title and description. The id never changes, so activity instances placed in courses
keep launching the same activity. The files live on disk in the activity's revision directories, behind
``generated_activity_dir(id)``; the row is what ties them to their owner.

A failure row is written only for an author's preview, and an activity keeps only its newest
``PXC_ACTION_FAILURE_LIMIT`` rows. An activity's failure rows are deleted with it.
"""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import DateTime, Enum
from sqlmodel import Column, Field, SQLModel, Text
from uuid6 import uuid7

from sparkth.lib.models import utc_now
from sparkth.plugins.pxc.enums import PreviewPermission, PxcFailureKind


def _enum_values(enum_cls: type[StrEnum]) -> list[str]:
    """The labels of an enum's DB type: its members' values, the strings stored in its column."""
    return [member.value for member in enum_cls]


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


class PxcActionFailure(SQLModel, table=True):
    """One action that failed or was refused in its author's preview, kept for the author's agent."""

    __tablename__ = "pxc_action_failures"

    id: UUID = Field(default_factory=uuid7, primary_key=True)
    activity_id: UUID = Field(foreign_key="pxc_activities.id", ondelete="CASCADE", index=True, nullable=False)
    # The revision the preview was pinned to, or None for an activity not yet kept in revisions.
    revision: str | None = Field(default=None, max_length=36, nullable=True)
    kind: PxcFailureKind = Field(
        sa_column=Column(Enum(PxcFailureKind, name="pxcfailurekind", values_callable=_enum_values), nullable=False)
    )
    action: str = Field(sa_column=Column(Text, nullable=False))
    permission: PreviewPermission = Field(
        sa_column=Column(
            Enum(PreviewPermission, name="previewpermission", values_callable=_enum_values), nullable=False
        )
    )
    value: str = Field(sa_column=Column(Text, nullable=False))
    error: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
