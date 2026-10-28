"""Explore's query and result models."""

from pydantic import BaseModel

from sparkth.core.analytics.explore.enums import Measure
from sparkth.core.analytics.reads.schemas import RangeQuery


class ExploreQuery(RangeQuery):
    """Query over one event type's raw events.

    ``filter`` items are ``field:value`` (``null`` matches a null or missing key); values of one field
    are ORed, fields ANDed. ``group_by`` is a field name or ``actor``.
    """

    event_type: str
    actor_id: str | None = None
    filter: list[str] = []
    measure: Measure = Measure.COUNT
    group_by: str | None = None


class ExplorePoint(BaseModel):
    """A measure for one bucket and group. ``bucket`` is the UTC start, ``YYYY-MM-DD``."""

    bucket: str
    group: str | None
    value: int


class ExploreTotal(BaseModel):
    """A group's measure over the whole range."""

    group: str | None
    value: int


class ExploreResult(BaseModel):
    """Explore points and totals; ``truncated`` when groups beyond the cap were dropped."""

    points: list[ExplorePoint]
    totals: list[ExploreTotal]
    truncated: bool
    actor_names: dict[str, str] = {}
