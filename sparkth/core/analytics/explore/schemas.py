"""Explore's query, result and saved-config models."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from pydantic.alias_generators import to_camel

from sparkth.core.analytics.explore.enums import ChartKind, Measure
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


ConfigText = Annotated[str, StringConstraints(max_length=100)]


class ViewFilter(BaseModel):
    """One filter: the field must equal the value."""

    model_config = ConfigDict(extra="forbid")

    field: ConfigText
    value: ConfigText


class ViewConfig(BaseModel):
    """An Explore config without the period, keyed as the frontend keeps it."""

    model_config = ConfigDict(extra="forbid", alias_generator=to_camel, populate_by_name=True)

    event: ConfigText | None = None
    actor: ConfigText | None = None
    filters: list[ViewFilter] = Field(default=[], max_length=20)
    measure: Measure = Measure.COUNT
    group_by: ConfigText | None = None
    chart: ChartKind = ChartKind.LINE
