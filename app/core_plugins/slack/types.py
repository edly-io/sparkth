"""Pydantic response schemas for the Slack TA Bot plugin."""

from datetime import datetime

from pydantic import BaseModel


class AuthorizationUrlResponse(BaseModel):
    url: str


class ConnectionStatusResponse(BaseModel):
    connected: bool
    team_name: str | None = None
    team_id: str | None = None
    bot_user_id: str | None = None
    connected_at: datetime | None = None


class BotResponseLogItem(BaseModel):
    id: int
    slack_channel: str
    slack_user: str
    question: str
    answer: str | None
    rag_matched: bool
    created_at: datetime


class LogsResponse(BaseModel):
    items: list[BotResponseLogItem]
    total: int
    next_cursor: int | None = None
    has_more: bool = False


class RagSourcesResponse(BaseModel):
    sources: list[str]
