"""Read-side queries over analytics data.

The read path never touches the application database — only analytics tables and
rollups. Exposed to the API layer and plugins via ``sparkth.lib.analytics``.

``read_rollup`` is dialect-aware because rollups only exist as TimescaleDB continuous
aggregates on PostgreSQL. On SQLite (the test / e2e database) the aggregates are not created,
so the same buckets are computed directly from ``raw_events``. Both queries are built from the
same arguments: same event types and payload-key dimensions, UTC day bucketing, the range
filtered on the day (inclusive both ends) before rolling days up into weeks (starting Monday)
or months (starting on the 1st). The identity holds as long as the caller's ``dims`` match
the aggregate's definition.

Day boundaries are UTC on both paths, and this is the premise that makes them
identical: PG's ``time_bucket('1 day', occurred_at)`` buckets the timestamptz in
UTC, while SQLite's ``date(occurred_at)`` buckets on the stored string's offset —
they agree only because the ingest path stores/interprets events as UTC. If the PG
side is ever parameterized with a bucketing timezone, the SQLite side must move in
lockstep or the two will silently diverge.
"""

import re
from collections.abc import Mapping, Sequence
from datetime import date

from sqlalchemy import RowMapping, bindparam, text
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.analytics.enums import Bucket
from sparkth.core.analytics.schemas.reads import LoginsPoint

# The queries are raw SQL rather than SQLAlchemy Core selects: the PostgreSQL one reads a
# TimescaleDB continuous aggregate, created by raw migration DDL and deliberately NOT registered
# as a ``sa.Table`` on ``analytics_metadata`` (Alembic autogenerate would try to create/drop it,
# and it doesn't exist on SQLite), and the two dialects need genuinely different queries anyway.

# Per-bucket SQL that reduces a timestamp to its bucket's first day (the day, its Monday, or the
# 1st), keyed by the enum so no request input ever reaches the SQL.
# PG: date_trunc('week') starts on Monday. SQLite: 'weekday 0' moves to the next Sunday
# (or stays on one), and '-6 days' steps back to that week's Monday.
_PG_BUCKET = {
    Bucket.day: "day AT TIME ZONE 'UTC'",
    Bucket.week: "date_trunc('week', day AT TIME ZONE 'UTC')",
    Bucket.month: "date_trunc('month', day AT TIME ZONE 'UTC')",
}
_SQLITE_BUCKET = {
    Bucket.day: "date(occurred_at)",
    Bucket.week: "date(occurred_at, 'weekday 0', '-6 days')",
    Bucket.month: "strftime('%Y-%m-01', occurred_at)",
}

# Everything interpolated into SQL must match these; event types may contain dots.
_NAME = re.compile(r"[a-z_][a-z0-9_]*")
_EVENT_TYPE = re.compile(r"[a-z_][a-z0-9_.]*")


def _safe(value: str, pattern: re.Pattern[str] = _NAME) -> str:
    if not pattern.fullmatch(value):
        raise ValueError(f"Unsafe SQL identifier: {value!r}")
    return value


def _sqlite_dim(key: str | Mapping[str, str]) -> str:
    if isinstance(key, str):
        return f"json_extract(payload, '$.{_safe(key)}')"
    whens = " ".join(
        f"WHEN '{_safe(event_type, _EVENT_TYPE)}' THEN json_extract(payload, '$.{_safe(k)}')"
        for event_type, k in key.items()
    )
    return f"CASE event_type {whens} END"


async def read_rollup(
    session: AsyncSession,
    *,
    aggregate: str,
    event_types: Sequence[str],
    dims: Mapping[str, str | Mapping[str, str]],
    by_event_type: bool = False,
    count_column: str,
    from_: date,
    to: date,
    bucket: Bucket,
) -> list[RowMapping]:
    """Count events per ``bucket`` (and ``dims``) for days ``from_``..``to`` (inclusive).

    PostgreSQL sums ``count_column`` of the continuous aggregate ``aggregate``, grouped by
    the aggregate's columns named like the ``dims`` keys; SQLite counts ``raw_events`` of
    ``event_types``, extracting each dim from the payload. The two agree only if ``dims``
    matches the aggregate's definition and ``count_column`` is the aggregate's count. The
    aggregate must have a ``day`` bucket column, and each dim must be a string-valued payload key.

    Args:
        aggregate: The continuous aggregate PostgreSQL reads.
        event_types: The event types SQLite counts.
        dims: Output column -> payload key, either one key for every event type or a
            per-event-type mapping (NULL for event types it omits). Payload keys are never SQL.
        by_event_type: Also group by ``event_type``.
        count_column: The aggregate's count column, also the output count's name.

    Returns:
        Rows of ``bucket`` (UTC start, ``YYYY-MM-DD``), ``event_type`` if requested, the dims
        and ``count_column``, sorted by everything but the count with NULLs first. Sparse.

    Raises:
        ValueError: A name, payload key or event type interpolated into SQL is unsafe.
    """
    _safe(aggregate)
    _safe(count_column)
    exprs = {_safe(name): _sqlite_dim(key) for name, key in dims.items()}
    group = ["event_type"] if by_event_type else []
    params: dict[str, object]
    if session.bind.dialect.name == "postgresql":
        cols = [*group, *dims]
        sql = text(
            f"SELECT to_char({_PG_BUCKET[bucket]}, 'YYYY-MM-DD') AS bucket, "
            + "".join(f"{c}, " for c in cols)
            + f"CAST(sum({count_column}) AS bigint) AS {count_column} FROM {aggregate} "
            "WHERE (day AT TIME ZONE 'UTC')::date BETWEEN :from_ AND :to "
            f"GROUP BY {', '.join(str(i) for i in range(1, len(cols) + 2))}"
        )
        params = {"from_": from_, "to": to}
    else:
        cols = [*group, *(f"{expr} AS {name}" for name, expr in exprs.items())]
        sql = text(
            f"SELECT {_SQLITE_BUCKET[bucket]} AS bucket, "
            + "".join(f"{c}, " for c in cols)
            + f"count(*) AS {count_column} FROM raw_events "
            "WHERE event_type IN :event_types AND date(occurred_at) BETWEEN :from_ AND :to "
            f"GROUP BY {', '.join(str(i) for i in range(1, len(cols) + 2))}"
        ).bindparams(bindparam("event_types", expanding=True))
        # SQLite compares the ISO strings date() produces.
        params = {"event_types": list(event_types), "from_": from_.isoformat(), "to": to.isoformat()}
    rows = (await session.execute(sql, params)).mappings().all()
    # Sorted here, NULLs first and bytewise: PG sorts NULLs last and its collation ignores
    # ``_``, SQLite compares bytes, so an ORDER BY would differ between the two.
    keys = ["bucket", *group, *dims]
    return sorted(rows, key=lambda r: [(r[k] is not None, r[k] or "") for k in keys])


async def get_logins(session: AsyncSession, from_: date, to: date, bucket: Bucket) -> list[LoginsPoint]:
    """Return login counts per ``bucket`` and sign-in method for days ``from_``..``to`` (inclusive).

    Oldest bucket first, methods ordered bytewise (NULLs first) within a bucket. Sparse: buckets or
    methods with no logins are omitted, so callers zero-fill.
    """
    rows = await read_rollup(
        session,
        aggregate="login_activity_daily_by_method",
        event_types=("user.logged_in",),
        dims={"method": "method"},
        count_column="login_count",
        from_=from_,
        to=to,
        bucket=bucket,
    )
    return [LoginsPoint.model_validate(dict(r)) for r in rows]
