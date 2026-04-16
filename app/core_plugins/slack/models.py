"""Database models for the Slack TA Bot plugin."""

from sqlalchemy import Text
from sqlmodel import Column, Field, SQLModel

from app.models.base import SoftDeleteModel, TimestampedModel


class SlackWorkspace(TimestampedModel, SoftDeleteModel, SQLModel, table=True):
    """Persisted Slack workspace connection per course author.

    One active row per user. Reconnecting overwrites the existing row.
    """

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
