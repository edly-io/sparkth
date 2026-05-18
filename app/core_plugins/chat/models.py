from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import field_validator
from sqlalchemy import DateTime, ForeignKey, Index, Integer, UniqueConstraint
from sqlmodel import Column, Field, Relationship, SQLModel, Text
from uuid6 import uuid7

from app.models.base import TimestampedModel

MessageType = Literal["text", "attachment"]


class Conversation(TimestampedModel, SQLModel, table=True):
    __tablename__ = "chat_conversations"
    __table_args__ = (
        Index("idx_user_created", "user_id", "created_at"),
        Index("idx_provider_model", "provider", "model"),
    )

    id: int | None = Field(default=None, primary_key=True)
    uuid: UUID = Field(default_factory=uuid7, unique=True, index=True)
    user_id: int = Field(foreign_key="user.id", index=True, nullable=False)
    llm_config_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("llm_configs.id", ondelete="SET NULL"),
            index=True,
            nullable=True,
        ),
    )
    provider: str = Field(max_length=50, nullable=False)
    model: str = Field(max_length=100, nullable=False)
    title: str | None = Field(default=None, max_length=255)
    system_prompt: str | None = Field(default=None, sa_column=Column(Text))
    total_tokens_used: int = Field(default=0)
    total_cost: float = Field(default=0.0)
    active_drive_file_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("drive_files.id", ondelete="SET NULL"),
            index=True,
            nullable=True,
        ),
    )
    active_drive_file_ids: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    messages: list["Message"] = Relationship(
        back_populates="conversation",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    attachments: list["ConversationAttachment"] = Relationship(
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "lazy": "select"}
    )


class Message(TimestampedModel, SQLModel, table=True):
    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("idx_conversation_created", "conversation_id", "created_at"),
        Index("idx_conversation_role", "conversation_id", "role"),
    )

    id: int | None = Field(default=None, primary_key=True)
    conversation_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("chat_conversations.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        ),
    )
    role: str = Field(max_length=20, nullable=False)
    content: str = Field(sa_column=Column(Text, nullable=False))
    tokens_used: int | None = Field(default=None)
    cost: float | None = Field(default=None)
    is_error: bool = Field(default=False)
    model_metadata: str | None = Field(default=None, sa_column=Column(Text))
    message_type: str = Field(default="text", max_length=20)
    attachment_name: str | None = Field(default=None, max_length=255)
    attachment_size: int | None = Field(default=None)
    conversation: Conversation = Relationship(back_populates="messages")

    @field_validator("message_type")
    @classmethod
    def validate_message_type(cls, v: str) -> str:
        allowed: tuple[MessageType, ...] = ("text", "attachment")
        if v not in allowed:
            raise ValueError(f"message_type must be one of {allowed}, got '{v}'")
        return v


class ConversationAttachment(TimestampedModel, SQLModel, table=True):
    """Join table linking conversations to attached Drive files."""

    __tablename__ = "chat_conversation_attachments"
    __table_args__ = (
        UniqueConstraint("conversation_id", "drive_file_id", name="uq_conv_attachment"),
        Index("idx_conv_attach_conversation", "conversation_id"),
        Index("idx_conv_attach_drive_file", "drive_file_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    conversation_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("chat_conversations.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    drive_file_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("drive_files.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    attached_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
