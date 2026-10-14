"""Read-side queries over analytics data.

The read path never touches the application database — only analytics tables and
rollups. Exposed to the API layer via ``sparkth.lib.analytics``.

Plugins build their own per-bucket SQL from ``PG_BUCKET`` / ``SQLITE_BUCKET`` and
run it with ``read_bucketed``; the PG/SQLite identity rule below applies to them too.

``get_logins`` is dialect-aware because the login rollup only exists as a TimescaleDB
continuous aggregate (``login_activity_daily_by_method``) on PostgreSQL. On SQLite (the test /
e2e database) the aggregate is not created, so the same buckets are computed directly from
``raw_events``. The two query variants below must stay semantically identical: same filter
(``user.logged_in``), UTC day bucketing, the range filtered on the day (inclusive both ends)
before rolling days up into weeks (starting Monday) or months (starting on the 1st), and one
row per bucket and sign-in method.

Day boundaries are UTC on both paths, and this is the premise that makes them
identical: PG's ``time_bucket('1 day', occurred_at)`` buckets the timestamptz in
UTC, while SQLite's ``date(occurred_at)`` buckets on the stored string's offset —
they agree only because the ingest path stores/interprets events as UTC. If the PG
side is ever parameterized with a bucketing timezone, the SQLite side must move in
lockstep or the two will silently diverge.
"""

from collections.abc import Mapping, Sequence
from datetime import date

from sqlalchemy import RowMapping, TextClause, text
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.analytics.enums import Bucket
from sparkth.core.analytics.schemas.reads import LoginsPoint

# The queries are raw SQL rather than SQLAlchemy Core selects: the PostgreSQL ones read a
# TimescaleDB continuous aggregate, created by raw migration DDL and deliberately NOT registered
# as a ``sa.Table`` on ``analytics_metadata`` (Alembic autogenerate would try to create/drop it,
# and it doesn't exist on SQLite), and the two dialects need genuinely different queries anyway.
# Writing them as side-by-side SQL strings makes the "must stay semantically identical"
# invariant easy to eyeball.

# Per-bucket SQL that reduces a timestamp to its bucket's first day (the day, its Monday, or the
# 1st), keyed by the enum so no request input ever reaches the SQL.
# PG: date_trunc('week') starts on Monday. SQLite: 'weekday 0' moves to the next Sunday
# (or stays on one), and '-6 days' steps back to that week's Monday.
PG_BUCKET = {
    Bucket.day: "day AT TIME ZONE 'UTC'",
    Bucket.week: "date_trunc('week', day AT TIME ZONE 'UTC')",
    Bucket.month: "date_trunc('month', day AT TIME ZONE 'UTC')",
}
SQLITE_BUCKET = {
    Bucket.day: "date(occurred_at)",
    Bucket.week: "date(occurred_at, 'weekday 0', '-6 days')",
    Bucket.month: "strftime('%Y-%m-01', occurred_at)",
}

_PG_LOGINS_SQL = {
    bucket: text(
        f"SELECT to_char({expr}, 'YYYY-MM-DD') AS bucket, method, "
        "CAST(sum(login_count) AS bigint) AS login_count "
        "FROM login_activity_daily_by_method "
        "WHERE (day AT TIME ZONE 'UTC')::date BETWEEN :from_ AND :to "
        "GROUP BY 1, method "
        "ORDER BY bucket, method"
    )
    for bucket, expr in PG_BUCKET.items()
}
_SQLITE_LOGINS_SQL = {
    bucket: text(
        f"SELECT {expr} AS bucket, json_extract(payload, '$.method') AS method, count(*) AS login_count "
        "FROM raw_events "
        "WHERE event_type = 'user.logged_in' "
        "AND date(occurred_at) BETWEEN :from_ AND :to "
        "GROUP BY 1, 2 "
        "ORDER BY bucket, method"
    )
    for bucket, expr in SQLITE_BUCKET.items()
}


async def read_bucketed(
    session: AsyncSession,
    pg_sql: Mapping[Bucket, TextClause],
    sqlite_sql: Mapping[Bucket, TextClause],
    from_: date,
    to: date,
    bucket: Bucket,
) -> Sequence[RowMapping]:
    """Run the ``bucket`` query for the session's dialect, binding ``:from_`` and ``:to``."""
    params: dict[str, date | str]
    if session.bind.dialect.name == "postgresql":
        sql, params = pg_sql[bucket], {"from_": from_, "to": to}
    else:
        # SQLite compares the ISO strings date() produces.
        sql, params = sqlite_sql[bucket], {"from_": from_.isoformat(), "to": to.isoformat()}
    return (await session.execute(sql, params)).mappings().all()


async def get_logins(session: AsyncSession, from_: date, to: date, bucket: Bucket) -> list[LoginsPoint]:
    """Return login counts per ``bucket`` and sign-in method for days ``from_``..``to`` (inclusive).

    Oldest bucket first, methods alphabetical within a bucket. Sparse: buckets or
    methods with no logins are omitted, so callers zero-fill.
    """
    rows = await read_bucketed(session, _PG_LOGINS_SQL, _SQLITE_LOGINS_SQL, from_, to, bucket)
    return [LoginsPoint(bucket=row["bucket"], method=row["method"], login_count=row["login_count"]) for row in rows]
