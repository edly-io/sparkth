"""Models the event catalog returns."""

from pydantic import BaseModel

from sparkth.core.analytics.catalog.enums import FilterFieldType


class EventField(BaseModel):
    """One payload field of an event type. ``values`` lists the choices of an ``enum``."""

    name: str
    kind: FilterFieldType
    values: list[str] | None = None
    nullable: bool = False


class EventCatalogEntry(BaseModel):
    """An event type and its payload fields, merged across versions."""

    event_type: str
    fields: list[EventField]
