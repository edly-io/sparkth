import json
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import AfterValidator, BaseModel, StringConstraints

from sparkth.plugins.pxc.config import get_pxc_settings


def within_source_limit(manifest: dict[str, object]) -> dict[str, object]:
    """Refuse a manifest whose JSON is longer than ``PXC_MAX_SOURCE_CHARS``, the cap on each script.

    Raises:
        ValueError: if the manifest is over the limit.
    """
    limit = get_pxc_settings().max_source_chars
    if len(json.dumps(manifest)) > limit:
        raise ValueError(f"manifest is longer than {limit} characters as JSON")
    return manifest


def script_within_source_limit(script: str) -> str:
    """Refuse a script longer than ``PXC_MAX_SOURCE_CHARS``.

    Raises:
        ValueError: if the script is over the limit.
    """
    limit = get_pxc_settings().max_source_chars
    if len(script) > limit:
        raise ValueError(f"script is longer than {limit} characters")
    return script


def description_within_limit(description: str) -> str:
    """Refuse a description longer than ``PXC_MAX_DESCRIPTION_CHARS``.

    Raises:
        ValueError: if the description is over the limit.
    """
    limit = get_pxc_settings().max_description_chars
    if len(description) > limit:
        raise ValueError(f"description is longer than {limit} characters")
    return description


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

    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    description: Annotated[str, AfterValidator(description_within_limit)]
    manifest: Annotated[dict[str, object], AfterValidator(within_source_limit)]
    ui_js: Annotated[str, AfterValidator(script_within_source_limit)]
    sandbox_js: Annotated[str, AfterValidator(script_within_source_limit)]
