"""Measure one event type's raw events per bucket, filtered and grouped by payload fields."""

from typing import Any

from sqlalchemy import ColumnClause, ColumnElement, case, func, literal_column, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from sparkth.core.analytics.catalog import EventField, FilterFieldType, catalog_entry, versions_with_kind
from sparkth.core.analytics.exceptions import (
    InvalidFilterValue,
    UngroupableExploreField,
    UnknownExploreEvent,
    UnknownExploreField,
)
from sparkth.core.analytics.explore.enums import Measure
from sparkth.core.analytics.explore.schemas import ExplorePoint, ExploreQuery, ExploreResult, ExploreTotal
from sparkth.core.analytics.models import raw_events
from sparkth.core.analytics.reads.buckets import PG_RAW_BUCKET, SQLITE_BUCKET, in_days
from sparkth.core.analytics.reads.enums import Bucket

GROUP_LIMIT = 20


def _fields(event_type: str) -> dict[str, EventField]:
    """The catalog's fields of ``event_type`` by name."""
    entry = catalog_entry(event_type)
    if entry is None:
        raise UnknownExploreEvent(event_type)
    return {field.name: field for field in entry.fields}


def _field(fields: dict[str, EventField], event_type: str, name: str) -> EventField:
    if name not in fields:
        raise UnknownExploreField(event_type, name)
    return fields[name]


def _typed(event_type: str, field: EventField, value: ColumnElement[Any]) -> ColumnElement[Any]:
    """``value`` only for rows whose version stores ``field`` as its kind, else NULL.

    An older version may store the field as another kind; the ``CASE`` keeps PostgreSQL from
    casting that row's value, and SQLite from coercing it.
    """
    versions = versions_with_kind(event_type, field.name, field.kind)
    return case((raw_events.c.event_version.in_(versions), value))


def _condition(event_type: str, field: EventField, value: str) -> ColumnElement[bool]:
    """Match ``field`` against one filter value, parsed by the field's kind."""
    column = raw_events.c.payload[field.name]
    match: ColumnElement[bool]
    if value == "null":
        match = column.as_string().is_(None)
    elif field.kind == FilterFieldType.boolean:
        if value not in ("true", "false"):
            raise InvalidFilterValue(field.name, value)
        match = _typed(event_type, field, column.as_boolean()) == (value == "true")
    elif field.kind == FilterFieldType.integer:
        try:
            number = int(value)
        except ValueError:
            raise InvalidFilterValue(field.name, value) from None
        if not -(2**31) <= number < 2**31:  # PG binds int4; a wider value fails the cast
            raise InvalidFilterValue(field.name, value)
        match = _typed(event_type, field, column.as_integer()) == number
    elif field.kind == FilterFieldType.enum and value not in (field.values or []):
        raise InvalidFilterValue(field.name, value)
    else:
        match = column.as_string() == value
    return match


def _filters(query: ExploreQuery, fields: dict[str, EventField]) -> list[ColumnElement[bool]]:
    """The query's conditions: event type, day range, field filters (ORed per field) and actor."""
    by_field: dict[str, list[ColumnElement[bool]]] = {}
    for item in query.filter:
        name, _, value = item.partition(":")
        field = _field(fields, query.event_type, name)
        by_field.setdefault(name, []).append(_condition(query.event_type, field, value))
    where = [
        raw_events.c.event_type == query.event_type,
        *in_days(query.from_, query.to),
        *(or_(*conditions) for conditions in by_field.values()),
    ]
    if query.actor_id is not None:
        where.append(raw_events.c.actor_id == query.actor_id)
    return where


def _grouping(
    query: ExploreQuery, fields: dict[str, EventField]
) -> tuple[ColumnElement[Any] | None, FilterFieldType | None]:
    """The column to group by, and its field's kind (``None`` for the actor or no grouping)."""
    if query.group_by is None:
        return None, None
    if query.group_by == "actor":
        return raw_events.c.actor_id, None
    field = _field(fields, query.event_type, query.group_by)
    column = raw_events.c.payload[field.name]
    if field.kind == FilterFieldType.integer:
        raise UngroupableExploreField(query.event_type, field.name)
    if field.kind == FilterFieldType.boolean:
        return _typed(query.event_type, field, column.as_boolean()), field.kind
    return column.as_string(), field.kind


def _bucket(dialect: str, bucket: Bucket) -> ColumnClause[str]:
    """Each event's bucket as ``YYYY-MM-DD``, its UTC start."""
    if dialect == "postgresql":
        return literal_column(f"to_char({PG_RAW_BUCKET[bucket]}, 'YYYY-MM-DD')")
    return literal_column(SQLITE_BUCKET[bucket])


def _label(value: Any, kind: FilterFieldType | None) -> str | None:
    """A group's label: booleans as ``true``/``false`` on every dialect, the rest as text."""
    if value is None:
        return None
    if kind == FilterFieldType.boolean:
        return "true" if value else "false"
    return str(value)


async def measure_raw_events(session: AsyncSession, query: ExploreQuery) -> ExploreResult:
    """Measure ``query.event_type`` per bucket and group, keeping the top ``GROUP_LIMIT`` groups.

    Totals come from a separate unbucketed query, so ``distinct_actors`` totals are distinct over
    the range. Groups rank by total, then name; points are sorted by bucket then group, ``None``
    first. ``actor_names`` is left empty.

    Raises:
        UnknownExploreEvent: The event type is not registered.
        UnknownExploreField: A filter or ``group_by`` names a field the event type lacks.
        InvalidFilterValue: A filter value does not fit its field's kind.
        UngroupableExploreField: ``group_by`` names an integer field.
    """
    fields = _fields(query.event_type)
    where = _filters(query, fields)
    group, kind = _grouping(query, fields)
    group_cols = [] if group is None else [group]
    measure = func.count() if query.measure == Measure.COUNT else func.count(raw_events.c.actor_id.distinct())

    # ponytail: scans raw_events, bounded by MAX_RANGE_DAYS; add an (event_type, occurred_at) index if slow.
    totals_rows = (await session.execute(select(*group_cols, measure).where(*where).group_by(*group_cols))).all()
    totals = sorted(
        (ExploreTotal(group=_label(r[0], kind) if group_cols else None, value=r[-1]) for r in totals_rows),
        key=lambda t: (-t.value, t.group is not None, t.group or ""),
    )
    kept = {t.group for t in totals[:GROUP_LIMIT]}

    bucket = _bucket(session.bind.dialect.name, query.bucket)
    # ponytail: fetches every group's buckets and drops all but the kept groups here; filter in SQL if slow.
    point_rows = await session.execute(select(bucket, *group_cols, measure).where(*where).group_by(bucket, *group_cols))
    points = [
        ExplorePoint(bucket=r[0], group=g, value=r[-1])
        for r in point_rows
        if (g := _label(r[1], kind) if group_cols else None) in kept
    ]
    points.sort(key=lambda p: (p.bucket, p.group is not None, p.group or ""))
    return ExploreResult(points=points, totals=totals[:GROUP_LIMIT], truncated=len(totals) > GROUP_LIMIT)
