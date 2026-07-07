"""Pydantic response schemas for the Slack TA Bot plugin."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class SlackAuthorizationUrlResponse(BaseModel):
    url: str


class SlackConnectionStatusResponse(BaseModel):
    connected: bool
    team_name: str | None = None
    team_id: str | None = None
    bot_user_id: str | None = None
    connected_at: datetime | None = None


class BotResponseLogItem(BaseModel):
    type: Literal["message"] = "message"
    id: int
    slack_channel: str
    slack_user: str
    slack_user_name: str | None = None
    slack_channel_name: str | None = None
    question: str
    answer: str | None
    rag_matched: bool
    response_type: str
    created_at: datetime


class ConnectionLogItem(BaseModel):
    type: Literal["connection"] = "connection"
    id: int
    event_type: str
    team_name: str | None = None
    created_at: datetime


LogItem = Annotated[BotResponseLogItem | ConnectionLogItem, Field(discriminator="type")]


class LogsResponse(BaseModel):
    items: list[LogItem]
    total: int
    next_cursor: str | None = None
    has_more: bool = False


class RagSourcesResponse(BaseModel):
    sources: list[str]
