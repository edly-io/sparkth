"""Read-side queries over analytics data.

The read path never touches the application database — only analytics tables and
rollups. Exposed to the API layer and plugins via ``sparkth.lib.analytics``.

``read_rollup`` is dialect-aware because rollups only exist as TimescaleDB continuous
aggregates on PostgreSQL. On SQLite (the test / e2e database) the aggregates are not created,
so the same buckets are computed directly from ``raw_events``. PostgreSQL reads the aggregate's
columns named like the ``dims`` keys; the aggregate's own definition fixes which event types and
payload keys they come from. SQLite filters ``raw_events`` to ``event_types`` and extracts each
dim from its payload key. Both bucket by UTC day and filter the range on the day (inclusive both
ends) before rolling days up into weeks (starting Monday) or months (starting on the 1st). The
two agree only when ``event_types`` and ``dims`` match the aggregate's definition.

Day boundaries are UTC on both paths, and this is the premise that makes them
identical: PG's ``time_bucket('1 day', occurred_at)`` buckets the timestamptz in
UTC, while SQLite's ``date(occurred_at)`` buckets on the stored string's offset —
they agree only because the ingest path stores/interprets events as UTC. If the PG
side is ever parameterized with a bucketing timezone, the SQLite side must move in
lockstep or the two will silently diverge.

It also holds the Overview's core figures (logins, active users, signups), seeded on the
``SUMMARY_FIGURES`` hook at import, and ``summarize``, which counts every registered figure for a
range and for the equal-length range before it.
"""

import re
from collections.abc import Mapping, Sequence
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import RowMapping, bindparam, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from sparkth.core.analytics.enums import Bucket
from sparkth.core.analytics.hooks import SUMMARY_FIGURES
from sparkth.core.analytics.models import raw_events
from sparkth.core.analytics.schemas.reads import LoginsPoint, SummaryCount
from sparkth.core.analytics.types import SummaryFigure
from sparkth.core.i18n import gettext, gettext_noop

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
# The same buckets over raw_events.occurred_at, for queries that read raw events on PostgreSQL.
_PG_RAW_BUCKET = {
    Bucket.day: "date_trunc('day', occurred_at AT TIME ZONE 'UTC')",
    Bucket.week: "date_trunc('week', occurred_at AT TIME ZONE 'UTC')",
    Bucket.month: "date_trunc('month', occurred_at AT TIME ZONE 'UTC')",
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
    sums: Mapping[str, str] | None = None,
    from_: date,
    to: date,
    bucket: Bucket,
) -> list[RowMapping]:
    """Count events per ``bucket`` (and ``dims``) for days ``from_``..``to`` (inclusive).

    PostgreSQL sums ``count_column`` of the continuous aggregate ``aggregate``, grouped by
    the aggregate's columns named like the ``dims`` keys; SQLite counts ``raw_events`` of
    ``event_types``, extracting each dim from the payload. The two agree only if ``dims``
    matches the aggregate's definition, ``count_column`` is the aggregate's count, and each
    ``sums`` output name is an aggregate column summing that payload key. The aggregate must
    have a ``day`` bucket column, and each dim must be a string-valued payload key.

    Args:
        aggregate: The continuous aggregate PostgreSQL reads.
        event_types: The event types SQLite counts.
        dims: Output column -> payload key, either one key for every event type or a
            per-event-type mapping (NULL for event types it omits). Payload keys are never SQL.
        by_event_type: Also group by ``event_type``.
        count_column: The aggregate's count column, also the output count's name.
        sums: Output column -> payload key to sum; PostgreSQL sums the aggregate's column of
            that output name. Each sum is an integer, 0 when there is nothing to sum.

    Returns:
        Rows of ``bucket`` (UTC start, ``YYYY-MM-DD``), ``event_type`` if requested, the dims
        and ``count_column``, then each sum, sorted by everything but the counts with NULLs
        first. Sparse.

    Raises:
        ValueError: A name, payload key or event type interpolated into SQL is unsafe.
    """
    _safe(aggregate)
    _safe(count_column)
    exprs = {_safe(name): _sqlite_dim(key) for name, key in dims.items()}
    sum_keys = {_safe(name): _safe(key) for name, key in (sums or {}).items()}
    group = ["event_type"] if by_event_type else []
    params: dict[str, object]
    if session.bind.dialect.name == "postgresql":
        cols = [*group, *dims]
        sql = text(
            f"SELECT to_char({_PG_BUCKET[bucket]}, 'YYYY-MM-DD') AS bucket, "
            + "".join(f"{c}, " for c in cols)
            + f"CAST(sum({count_column}) AS bigint) AS {count_column}"
            + "".join(f", CAST(coalesce(sum({name}), 0) AS bigint) AS {name}" for name in sum_keys)
            + f" FROM {aggregate} "
            "WHERE (day AT TIME ZONE 'UTC')::date BETWEEN :from_ AND :to "
            f"GROUP BY {', '.join(str(i) for i in range(1, len(cols) + 2))}"
        )
        params = {"from_": from_, "to": to}
    else:
        cols = [*group, *(f"{expr} AS {name}" for name, expr in exprs.items())]
        sql = text(
            f"SELECT {_SQLITE_BUCKET[bucket]} AS bucket, "
            + "".join(f"{c}, " for c in cols)
            + f"count(*) AS {count_column}"
            + "".join(
                f", CAST(coalesce(sum(json_extract(payload, '$.{key}')), 0) AS integer) AS {name}"
                for name, key in sum_keys.items()
            )
            + " FROM raw_events "
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

    Oldest bucket first, methods ordered bytewise (``unknown`` first) within a bucket. Sparse:
    buckets or methods with no logins are omitted, so callers zero-fill. A login whose payload has
    no ``method`` counts as ``unknown``.
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
    return [LoginsPoint.model_validate({**r, "method": r["method"] or "unknown"}) for r in rows]


def _in_days(from_: date, to: date) -> tuple[Any, Any]:
    # A datetime range, not date(occurred_at), so one query serves both dialects.
    start = datetime.combine(from_, time(), timezone.utc)
    end = datetime.combine(to + timedelta(days=1), time(), timezone.utc)
    return raw_events.c.occurred_at >= start, raw_events.c.occurred_at < end


async def _logins(session: AsyncSession, from_: date, to: date) -> int:
    return sum(p.login_count for p in await get_logins(session, from_, to, Bucket.month))


async def _active_users(session: AsyncSession, from_: date, to: date) -> int:
    # ponytail: scans raw_events over the range; add an (occurred_at, actor_id) index or a daily
    # distinct-actor rollup if it gets slow. Aggregates can't count distinct across days.
    query = select(func.count(raw_events.c.actor_id.distinct())).where(*_in_days(from_, to))
    return int(await session.scalar(query) or 0)


async def _signups(session: AsyncSession, from_: date, to: date) -> int:
    query = select(func.count()).where(raw_events.c.event_type == "user.registered", *_in_days(from_, to))
    return int(await session.scalar(query) or 0)


SUMMARY_FIGURES.add_item(SummaryFigure("logins", gettext_noop("Logins"), _logins, view="logins", order=10))
SUMMARY_FIGURES.add_item(SummaryFigure("active_users", gettext_noop("Active users"), _active_users, order=20))
SUMMARY_FIGURES.add_item(SummaryFigure("signups", gettext_noop("Signups"), _signups, order=30))


async def summarize(session: AsyncSession, from_: date, to: date) -> list[SummaryCount]:
    """Count every registered figure for ``from_``..``to`` and for the same number of days before.

    Labels are translated into the request locale. Ordered by ``order``, then ``key``.
    """
    prev_to = from_ - timedelta(days=1)
    prev_from = prev_to - (to - from_)
    figures = sorted(SUMMARY_FIGURES.iter_values(), key=lambda f: (f.order, f.key))
    # ponytail: one query per figure and period, in sequence (one session). Batch them if the
    # figure count grows.
    return [
        SummaryCount(
            key=f.key,
            label=gettext(f.label),
            view=f.view,
            plugin=f.plugin,
            current=await f.count(session, from_, to),
            previous=await f.count(session, prev_from, prev_to),
        )
        for f in figures
    ]
