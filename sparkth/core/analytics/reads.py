"""Read-side queries over analytics data.

The read path never touches the application database — only analytics tables and
rollups. Exposed to the API layer via ``sparkth.lib.analytics``.

``get_login_activity`` is dialect-aware because the login-activity rollup only
exists as a TimescaleDB continuous aggregate on PostgreSQL. On SQLite (the test /
e2e database) the aggregate is not created (see the analytics migration), so we
compute the same daily buckets directly from ``raw_events``. The two query variants
below must stay semantically identical — same filter (``user.logged_in``), same
day bucketing, same columns, and same date-floor window (last ``days`` calendar
days).

Day boundaries are UTC on both paths, and this is the premise that makes them
identical: PG's ``time_bucket('1 day', occurred_at)`` buckets the timestamptz in
UTC, while SQLite's ``date(occurred_at)`` buckets on the stored string's offset —
they agree only because the ingest path stores/interprets events as UTC. If the PG
side is ever parameterized with a bucketing timezone, the SQLite side must move in
lockstep or the two will silently diverge.
"""

from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession


class LoginActivityPoint(BaseModel):
    """One day's login count. ``day`` is an ISO ``YYYY-MM-DD`` string."""

    day: str
    login_count: int


# Both queries are raw SQL rather than SQLAlchemy Core selects, for two reasons:
#   1. The PostgreSQL query reads ``login_activity_daily`` — the TimescaleDB continuous
#      aggregate. That relation is created by raw migration DDL and is deliberately NOT
#      registered as a ``sa.Table`` on ``analytics_metadata`` (doing so would make Alembic
#      autogenerate try to create/drop it, and it doesn't exist on SQLite). With no table
#      object to select against, a Core query would need a throwaway Table declaration plus
#      Postgres-only funcs (``to_char``) — i.e. the same SQL with more ceremony.
#   2. The two dialects need genuinely different queries (different source relation, different
#      day-bucketing), so Core could not unify them anyway. Writing them as two side-by-side
#      SQL strings makes the "must stay semantically identical" invariant (see module docstring)
#      easy to eyeball. ``raw_events`` IS a ``sa.Table``, so the SQLite branch could be Core, but
#      mixing one Core branch with one raw branch would obscure that pairing.

# PostgreSQL: read the pre-rolled continuous aggregate.
_PG_SQL = text(
    "SELECT to_char(day AT TIME ZONE 'UTC', 'YYYY-MM-DD') AS day, login_count "
    "FROM login_activity_daily "
    "WHERE (day AT TIME ZONE 'UTC')::date >= (now() AT TIME ZONE 'UTC')::date - :days "
    "ORDER BY day DESC "
    "LIMIT :days"
)

# SQLite (tests/e2e): aggregate raw_events directly — same semantics as the cagg.
_SQLITE_SQL = text(
    "SELECT date(occurred_at) AS day, count(*) AS login_count "
    "FROM raw_events "
    "WHERE event_type = 'user.logged_in' "
    "AND date(occurred_at) >= date('now', '-' || :days || ' days') "
    "GROUP BY date(occurred_at) "
    "ORDER BY day DESC "
    "LIMIT :days"
)


async def get_login_activity(session: AsyncSession, days: int = 30) -> list[LoginActivityPoint]:
    """Return daily login counts, newest first, for the last ``days`` calendar days.

    The window is bounded by a date floor (``now - days``), so gap days never let
    the series reach back beyond the requested window. Days with no logins are
    omitted entirely — the series is not zero-filled; callers must tolerate gaps.
    """
    dialect = session.bind.dialect.name
    sql = _PG_SQL if dialect == "postgresql" else _SQLITE_SQL
    rows = (await session.execute(sql, {"days": days})).mappings().all()
    return [LoginActivityPoint(day=str(row["day"]), login_count=row["login_count"]) for row in rows]
