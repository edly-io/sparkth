"""Request and response bodies of the saved Explore views API."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints

from sparkth.lib.analytics import ViewConfig

ViewName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class AnalyticsViewIn(BaseModel):
    """A view to save."""

    name: ViewName
    config: ViewConfig


class AnalyticsViewPatch(BaseModel):
    """Parts of a view to change."""

    name: ViewName | None = None
    config: ViewConfig | None = None


class AnalyticsViewOut(BaseModel):
    """A saved view."""

    id: uuid.UUID
    name: str
    config: ViewConfig
    created_at: datetime
    updated_at: datetime
