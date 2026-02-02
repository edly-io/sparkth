from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)


class TimestampedModel(SQLModel):
    created_at: datetime = Field(
        sa_type=DateTime(timezone=True),  # type: ignore
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: datetime = Field(
        sa_type=DateTime(timezone=True),  # type: ignore
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def update_timestamp(self) -> None:
        self.updated_at = datetime.now(timezone.utc)


class SoftDeleteModel(SQLModel):
    is_deleted: bool = Field(default=False, index=True)

    deleted_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
