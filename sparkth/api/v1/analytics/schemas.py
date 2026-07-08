"""Request and response schemas for the analytics events endpoint."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class EmitEventRequest(BaseModel):
    event_type: str
    version: int
    payload: dict[str, Any]
    occurred_at: datetime | None = None


class EmitEventResponse(BaseModel):
    accepted: bool
