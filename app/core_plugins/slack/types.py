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
