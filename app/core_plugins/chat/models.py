from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer
from sqlmodel import Column, Field, Relationship, SQLModel, Text

from app.models.base import SoftDeleteModel, TimestampedModel


class ProviderAPIKey(TimestampedModel, SoftDeleteModel, SQLModel, table=True):
    __tablename__ = "chat_provider_api_keys"
    __table_args__ = (Index("idx_user_provider_active", "user_id", "provider", "is_active"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True, nullable=False)
    provider: str = Field(max_length=50, index=True, nullable=False)
    encrypted_key: str = Field(sa_column=Column(Text, nullable=False))
    is_active: bool = Field(default=True)
    last_used_at: datetime | None = Field(
        default=None,
        sa_column_kwargs={"server_default": None},
    )

    conversations: list["Conversation"] = Relationship(back_populates="api_key")


class Conversation(TimestampedModel, SQLModel, table=True):
    __tablename__ = "chat_conversations"
    __table_args__ = (
        Index("idx_user_created", "user_id", "created_at"),
        Index("idx_provider_model", "provider", "model"),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True, nullable=False)
    api_key_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("chat_provider_api_keys.id", ondelete="SET NULL"),
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

    api_key: ProviderAPIKey | None = Relationship(back_populates="conversations")
    messages: list["Message"] = Relationship(
        back_populates="conversation",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
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
    model_metadata: str | None = Field(default=None, sa_column=Column(Text))
    conversation: Conversation = Relationship(back_populates="messages")
