from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from sparkth.plugins.pxc.constants import PXC_MAX_DESCRIPTION_CHARS, PXC_MAX_SOURCE_CHARS


class LaunchContext(BaseModel):
    """The identifiers the activity's client code needs, mirroring PXC's context shape."""

    activity_id: str
    course_id: str
    user_id: str


class ActivityConfig(BaseModel):
    """Everything the embed shell needs to render one activity for one learner, inlined into its page."""

    activity: str
    context: LaunchContext
    permission: str
    state: dict[str, Any]
    ui_url: str
    asset_base_url: str
    action_base_url: str
    ws_url: str


class ActivitySummary(BaseModel):
    """One of an author's activities, as the Activities page lists it."""

    id: UUID
    title: str
    description: str
    created_at: datetime
    preview_url: str


class ActivityLaunch(BaseModel):
    """Where the preview page iframes one activity for its author."""

    embed_url: str


class ActivitySource(BaseModel):
    """The files an agent writes for one activity, and how the activity is listed."""

    title: str = Field(min_length=1, max_length=255)
    description: str = Field(max_length=PXC_MAX_DESCRIPTION_CHARS)
    manifest: dict[str, object]
    ui_js: str = Field(max_length=PXC_MAX_SOURCE_CHARS)
    sandbox_js: str = Field(max_length=PXC_MAX_SOURCE_CHARS)
