"""Explore: count one event type's raw events per bucket, filtered and grouped by payload fields."""

from typing import Any

from sqlalchemy import ColumnClause, ColumnElement, func, literal_column, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from sparkth.core.analytics.catalog import catalog_entry
from sparkth.core.analytics.exceptions import (
    ExploreQueryError,
    InvalidFilterValue,
    UnknownExploreEvent,
    UnknownExploreField,
)
from sparkth.core.analytics.models import raw_events
from sparkth.core.analytics.reads import _PG_RAW_BUCKET, _SQLITE_BUCKET, _in_days
from sparkth.core.analytics.schemas.reads import (
    EventField,
    ExplorePoint,
    ExploreQuery,
    ExploreResult,
    ExploreTotal,
    FieldKind,
    Measure,
)

GROUP_LIMIT = 20


def _condition(field: EventField, value: str) -> ColumnElement[bool]:
    """Match ``field`` against one filter value, parsed by the field's kind."""
    column = raw_events.c.payload[field.name]
    match: ColumnElement[bool]
    if value == "null":
        match = column.as_string().is_(None)
    elif field.kind == FieldKind.boolean:
        if value not in ("true", "false"):
            raise InvalidFilterValue(field.name, value)
        match = column.as_boolean() == (value == "true")
    elif field.kind == FieldKind.integer:
        try:
            number = int(value)
        except ValueError:
            raise InvalidFilterValue(field.name, value) from None
        if not -(2**31) <= number < 2**31:  # PG binds int4; a wider value fails the cast
            raise InvalidFilterValue(field.name, value)
        match = column.as_integer() == number
    elif field.kind == FieldKind.enum and value not in (field.values or []):
        raise InvalidFilterValue(field.name, value)
    else:
        match = column.as_string() == value
    return match


def _group_value(value: Any, kind: FieldKind | None) -> str | None:
    """A group's label: booleans as ``true``/``false`` on every dialect, the rest as text."""
    if value is None:
        return None
    if kind == FieldKind.boolean:
        return "true" if value else "false"
    return str(value)


async def explore(session: AsyncSession, query: ExploreQuery) -> ExploreResult:
    """Measure ``query.event_type`` per bucket and group, keeping the top ``GROUP_LIMIT`` groups.

    Totals come from a separate unbucketed query, so ``distinct_actors`` totals are distinct over
    the range. Groups rank by total, then name; points are sorted by bucket then group, ``None``
    first. ``actor_names`` is left empty.

    Raises:
        UnknownExploreEvent: The event type is not registered.
        UnknownExploreField: A filter or ``group_by`` names a field the event type lacks.
        InvalidFilterValue: A filter value does not fit its field's kind.
        ExploreQueryError: ``group_by`` names an integer field.
    """
    entry = catalog_entry(query.event_type)
    if entry is None:
        raise UnknownExploreEvent(query.event_type)
    fields = {f.name: f for f in entry.fields}

    by_field: dict[str, list[ColumnElement[bool]]] = {}
    for item in query.filter:
        name, _, value = item.partition(":")
        if name not in fields:
            raise UnknownExploreField(query.event_type, name)
        by_field.setdefault(name, []).append(_condition(fields[name], value))
    where = [
        raw_events.c.event_type == query.event_type,
        *_in_days(query.from_, query.to),
        *(or_(*conditions) for conditions in by_field.values()),
    ]
    if query.actor_id is not None:
        where.append(raw_events.c.actor_id == query.actor_id)

    group: Any = None
    kind: FieldKind | None = None
    if query.group_by == "actor":
        group = raw_events.c.actor_id
    elif query.group_by is not None:
        if query.group_by not in fields:
            raise UnknownExploreField(query.event_type, query.group_by)
        kind = fields[query.group_by].kind
        column = raw_events.c.payload[query.group_by]
        if kind == FieldKind.integer:
            raise ExploreQueryError(f"Cannot group by integer field '{query.group_by}'")
        group = column.as_boolean() if kind == FieldKind.boolean else column.as_string()

    measure = func.count() if query.measure == Measure.COUNT else func.count(raw_events.c.actor_id.distinct())
    group_cols = [] if group is None else [group]
    if session.bind.dialect.name == "postgresql":
        bucket_sql = f"to_char({_PG_RAW_BUCKET[query.bucket]}, 'YYYY-MM-DD')"
    else:
        bucket_sql = _SQLITE_BUCKET[query.bucket]
    bucket: ColumnClause[str] = literal_column(bucket_sql)

    # ponytail: scans raw_events, bounded by MAX_RANGE_DAYS; add an (event_type, occurred_at) index if slow.
    totals_rows = (await session.execute(select(*group_cols, measure).where(*where).group_by(*group_cols))).all()
    totals = sorted(
        (ExploreTotal(group=_group_value(r[0], kind) if group_cols else None, value=r[-1]) for r in totals_rows),
        key=lambda t: (-t.value, t.group is not None, t.group or ""),
    )
    kept = {t.group for t in totals[:GROUP_LIMIT]}

    # ponytail: fetches every group's buckets and drops all but the kept groups here; filter in SQL if slow.
    point_rows = await session.execute(select(bucket, *group_cols, measure).where(*where).group_by(bucket, *group_cols))
    points = [
        ExplorePoint(bucket=r[0], group=g, value=r[-1])
        for r in point_rows
        if (g := _group_value(r[1], kind) if group_cols else None) in kept
    ]
    points.sort(key=lambda p: (p.bucket, p.group is not None, p.group or ""))
    return ExploreResult(points=points, totals=totals[:GROUP_LIMIT], truncated=len(totals) > GROUP_LIMIT)
