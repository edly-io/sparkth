from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime
from sqlmodel import Field
from uuid6 import uuid7

from .base import SoftDeleteModel, TimestampedModel


class User(TimestampedModel, SoftDeleteModel, table=True):
    __tablename__ = "user"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=30)
    username: str = Field(max_length=20, unique=True, index=True)
    email: str = Field(max_length=50, unique=True, index=True)
    hashed_password: str | None = Field(default=None)
    google_id: str | None = Field(default=None, unique=True, index=True)

    uuid: UUID = Field(default_factory=uuid7, unique=True, index=True)

    is_superuser: bool = Field(default=False)

    email_verified: bool = Field(default=False)
    email_verified_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
