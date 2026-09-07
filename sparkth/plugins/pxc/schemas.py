from typing import Any

from pydantic import BaseModel


class LaunchContext(BaseModel):
    """The identifiers the activity's client code needs, mirroring PXC's context shape."""

    activity_id: str
    course_id: str
    user_id: str


class ActivityConfig(BaseModel):
    """Everything the embed shell needs to render one activity for one learner."""

    activity: str
    context: LaunchContext
    permission: str
    state: dict[str, Any]
    ui_url: str
    asset_base_url: str
    action_base_url: str


class ActionResult(BaseModel):
    """The events one action produced, returned in the same response that submitted it."""

    events: list[dict[str, Any]]
