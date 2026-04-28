from sqlmodel import Field

from .base import TimestampedModel


class WhitelistedEmail(TimestampedModel, table=True):
    __tablename__ = "whitelisted_email"

    id: int | None = Field(default=None, primary_key=True)
    value: str = Field(max_length=255, unique=True, index=True)
    entry_type: str = Field(max_length=10)  # "email" or "domain"
    added_by_id: int | None = Field(default=None, foreign_key="user.id")
