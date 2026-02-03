from datetime import datetime
from typing import Optional

from sqlalchemy import Index
from sqlmodel import Column, Field, Relationship, SQLModel, Text

from app.models.base import SoftDeleteModel, TimestampedModel


class ProviderAPIKey(TimestampedModel, SoftDeleteModel, SQLModel, table=True):
    __tablename__ = "chat_provider_api_keys"
    __table_args__ = (Index("idx_user_provider_active", "user_id", "provider", "is_active"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True, nullable=False)
    provider: str = Field(max_length=50, index=True, nullable=False)
    encrypted_key: str = Field(sa_column=Column(Text, nullable=False))
    is_active: bool = Field(default=True)
    last_used_at: Optional[datetime] = Field(
        default=None,
        sa_column_kwargs={"server_default": None},
    )

    conversations: list["Conversation"] = Relationship(back_populates="api_key")


class Conversation(TimestampedModel, SoftDeleteModel, SQLModel, table=True):
    __tablename__ = "chat_conversations"
    __table_args__ = (
        Index("idx_user_created", "user_id", "created_at"),
        Index("idx_provider_model", "provider", "model"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True, nullable=False)
    api_key_id: int = Field(foreign_key="chat_provider_api_keys.id", index=True, nullable=False)
    provider: str = Field(max_length=50, nullable=False)
    model: str = Field(max_length=100, nullable=False)
    title: Optional[str] = Field(default=None, max_length=255)
    system_prompt: Optional[str] = Field(default=None, sa_column=Column(Text))
    total_tokens_used: int = Field(default=0)
    total_cost: float = Field(default=0.0)

    api_key: ProviderAPIKey = Relationship(back_populates="conversations")
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

    id: Optional[int] = Field(default=None, primary_key=True)
    conversation_id: int = Field(foreign_key="chat_conversations.id", index=True, nullable=False)
    role: str = Field(max_length=20, nullable=False)
    content: str = Field(sa_column=Column(Text, nullable=False))
    tokens_used: Optional[int] = Field(default=None)
    cost: Optional[float] = Field(default=None)
    model_metadata: Optional[str] = Field(default=None, sa_column=Column(Text))
    conversation: Conversation = Relationship(back_populates="messages")
