"""Event catalog: registered event types and their payload fields, from the ``ANALYTICS_EVENTS`` hook."""

from enum import StrEnum
from types import UnionType
from typing import Annotated, Literal, Union, get_args, get_origin

from pydantic.fields import FieldInfo

from sparkth.core.analytics import ANALYTICS_EVENTS
from sparkth.core.analytics.schemas.reads import EventCatalogEntry, EventField, FilterFieldType


def _field(name: str, info: FieldInfo) -> EventField | None:
    """Describe one payload field, or ``None`` when its type is not filterable."""
    annotation = info.annotation
    nullable = False
    if get_origin(annotation) in (Union, UnionType):
        args = [a for a in get_args(annotation) if a is not type(None)]
        nullable = len(args) < len(get_args(annotation))
        annotation = args[0] if len(args) == 1 else None
    if get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]
    if get_origin(annotation) is Literal:
        return EventField(
            name=name, kind=FilterFieldType.enum, values=[str(v) for v in get_args(annotation)], nullable=nullable
        )
    if not isinstance(annotation, type):
        return None
    if issubclass(annotation, StrEnum):
        return EventField(name=name, kind=FilterFieldType.enum, values=[m.value for m in annotation], nullable=nullable)
    for python_type, kind in (
        (bool, FilterFieldType.boolean),
        (int, FilterFieldType.integer),
        (str, FilterFieldType.string),
    ):
        if issubclass(annotation, python_type):
            return EventField(name=name, kind=kind, nullable=nullable)
    return None


def event_catalog() -> list[EventCatalogEntry]:
    """Every event type with its fields merged across versions (the highest version wins), sorted."""
    merged: dict[str, dict[str, EventField]] = {}
    for schema in sorted(ANALYTICS_EVENTS.iter_values(), key=lambda s: s.version):
        fields = merged.setdefault(schema.event_type, {})
        for name, info in schema.model_fields.items():
            if (field := _field(name, info)) is not None:
                fields[name] = field
    return [
        EventCatalogEntry(event_type=event_type, fields=sorted(fields.values(), key=lambda field: field.name))
        for event_type, fields in sorted(merged.items())
    ]


def catalog_entry(event_type: str) -> EventCatalogEntry | None:
    """The catalog entry for ``event_type``, or ``None`` when it is not registered."""
    return next((e for e in event_catalog() if e.event_type == event_type), None)
