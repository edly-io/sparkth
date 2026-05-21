"""Database models for the Slack TA Bot plugin."""

from enum import Enum

from sqlalchemy import Column, Text
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlmodel import Field, SQLModel

from app.models.base import SoftDeleteModel, TimestampedModel


class ResponseType(str, Enum):
    rag_match = "rag_match"
    fallback = "fallback"
    greeting = "greeting"
    config_incomplete = "config_incomplete"
    plugin_disabled = "plugin_disabled"
    legacy = "legacy"
    no_files_resolved = "no_files_resolved"
    rag_not_ready = "rag_not_ready"
    drive_file_not_found = "drive_file_not_found"
    retrieval_error = "retrieval_error"


class ConnectionEventType(str, Enum):
    connected = "connected"
    disconnected = "disconnected"


class SlackWorkspace(TimestampedModel, SoftDeleteModel, SQLModel, table=True):
    """Persisted Slack workspace connection per course author."""

    __tablename__ = "slack_workspaces"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True, nullable=False)
    team_id: str = Field(max_length=50, index=True, nullable=False)
    team_name: str = Field(max_length=255, nullable=False)
    bot_token_encrypted: str = Field(sa_column=Column(Text, nullable=False))
    bot_user_id: str = Field(max_length=50, nullable=False)
    is_active: bool = Field(default=True, index=True)


class BotResponseLog(TimestampedModel, SQLModel, table=True):
    """Audit log for every answer the TA Bot posts to Slack."""

    __tablename__ = "slack_bot_response_logs"

    id: int | None = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="slack_workspaces.id", index=True, nullable=False)
    slack_channel: str = Field(max_length=50, nullable=False)
    slack_user: str = Field(max_length=50, nullable=False)
    slack_ts: str = Field(max_length=50, nullable=False)
    question: str = Field(sa_column=Column(Text, nullable=False))
    answer: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    rag_matched: bool = Field(default=False, nullable=False)
    response_type: ResponseType = Field(
        sa_column=Column(
            SQLAlchemyEnum(ResponseType, name="responsetype"),
            nullable=False,
            server_default="legacy",
        )
    )
    slack_user_name: str | None = Field(default=None, max_length=255, nullable=True)
    slack_channel_name: str | None = Field(default=None, max_length=255, nullable=True)


class SlackConnectionLog(TimestampedModel, SQLModel, table=True):
    """Audit log for Slack workspace connect and disconnect events."""

    __tablename__ = "slack_connection_logs"

    id: int | None = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="slack_workspaces.id", index=True, nullable=False)
    event_type: ConnectionEventType = Field(
        sa_column=Column(
            SQLAlchemyEnum(ConnectionEventType, name="connectioneventtype"),
            nullable=False,
        )
    )
    team_name: str | None = Field(default=None, max_length=255, nullable=True)
