"""LLMConfig — centralized LLM provider credential model."""

from datetime import datetime

from sqlalchemy import Column, Index, Text, text
from sqlmodel import DateTime, Field, SQLModel

from app.models.base import SoftDeleteModel, TimestampedModel


class LLMConfig(TimestampedModel, SoftDeleteModel, SQLModel, table=True):
    __tablename__ = "llm_configs"
    __table_args__ = (
        Index(
            "uq_user_llm_config_name_active",
            "user_id",
            "name",
            unique=True,
            postgresql_where=text("is_deleted = false"),
            sqlite_where=text("is_deleted = 0"),
        ),
        Index("idx_llm_config_user", "user_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    name: str = Field(max_length=100)
    provider: str = Field(max_length=50)
    model: str = Field(max_length=100)
    encrypted_key: str = Field(sa_column=Column(Text, nullable=False))
    masked_key: str = Field(sa_column=Column(Text, nullable=False))
    is_active: bool = Field(default=True)
    last_used_at: datetime | None = Field(
        sa_type=DateTime(timezone=True),  # type: ignore
        default=None,
        nullable=True,
    )
