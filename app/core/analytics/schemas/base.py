"""Shared base for all analytics event payload schemas."""

from pydantic import BaseModel, ConfigDict


class AnalyticsEventSchema(BaseModel):
    """Base class for analytics event payload schemas.

    Extra fields are forbidden so a producer sending unexpected keys gets a
    ``422`` rather than having those fields silently dropped from the stored row.
    """

    model_config = ConfigDict(extra="forbid")
