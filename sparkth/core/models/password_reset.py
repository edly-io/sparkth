from datetime import datetime

from sqlalchemy import Column, ForeignKey, Integer
from sqlmodel import Field

from .base import TimestampedModel, TZDateTime


class PasswordResetToken(TimestampedModel, table=True):
    """A single-use password reset link, stored as the SHA-256 hash of its token."""

    __tablename__ = "password_reset_token"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    token_hash: str = Field(max_length=64, unique=True)
    expires_at: datetime = Field(sa_column=Column(TZDateTime(), nullable=False))
    used_at: datetime | None = Field(default=None, sa_column=Column(TZDateTime()))
