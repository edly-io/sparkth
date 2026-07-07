"""Database models for the Slack TA Bot plugin."""

from sqlalchemy import Column, Index, Text, text
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlmodel import Field, SQLModel

from sparkth.models.base import SoftDeleteModel, TimestampedModel
from sparkth.plugins.slack.enums import ConnectionEventType, ResponseType


class SlackWorkspace(TimestampedModel, SoftDeleteModel, SQLModel, table=True):
    """Persisted Slack workspace connection per course author."""

    __tablename__ = "slack_workspaces"
    __table_args__ = (
        Index(
            "uq_slack_workspaces_team_id_active",
            "team_id",
            unique=True,
            postgresql_where=text("is_active = true AND is_deleted = false"),
            sqlite_where=text("is_active = 1 AND is_deleted = 0"),
        ),
        Index(
            "uq_slack_workspaces_user_id_active",
            "user_id",
            unique=True,
            postgresql_where=text("is_active = true AND is_deleted = false"),
            sqlite_where=text("is_active = 1 AND is_deleted = 0"),
        ),
    )

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
            SQLAlchemyEnum(ResponseType, name="responsetype", values_callable=lambda e: [m.value for m in e]),
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
            SQLAlchemyEnum(
                ConnectionEventType, name="connectioneventtype", values_callable=lambda e: [m.value for m in e]
            ),
            nullable=False,
        )
    )
    team_name: str | None = Field(default=None, max_length=255, nullable=True)
