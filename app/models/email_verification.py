from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer
from sqlmodel import Field

from .base import TimestampedModel


class EmailVerificationToken(TimestampedModel, table=True):
    __tablename__ = "email_verification_token"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    token_hash: str = Field(max_length=64, unique=True, index=True)
    expires_at: datetime = Field(
        sa_type=DateTime(timezone=True),  # type: ignore
        nullable=False,
    )
    used_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
