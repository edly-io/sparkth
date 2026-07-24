from datetime import datetime, timezone

from sqlalchemy import DateTime, Dialect
from sqlalchemy.types import TypeDecorator
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)


class TZDateTime(TypeDecorator[datetime]):
    """Column type for datetimes that are timezone-aware UTC on both sides.

    PostgreSQL stores timestamptz natively, but SQLite drops the UTC offset on
    storage, so values that read back naive are re-tagged as UTC. Naive
    datetimes are rejected on write — callers must store aware values
    (see :func:`utc_now`).
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("TZDateTime columns require timezone-aware datetimes")
        return value

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


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

    def soft_delete(self) -> None:
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)

    def restore(self) -> None:
        self.is_deleted = False
        self.deleted_at = None
