"""TimescaleDB-backed tests for login-activity reads (the ``pg``-marked lane).

These exercise the production PostgreSQL path — ``_PG_SQL`` reading the
``login_activity_daily`` continuous aggregate created by the analytics migrations —
which the SQLite suite can only imitate. They make the "both dialect variants must stay
semantically identical" invariant executable instead of eyeball-checked.
"""

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.analytics.reads import LoginActivityPoint, get_login_activity
from sparkth.lib.analytics import ingest_event

pytestmark = pytest.mark.pg


def _days_ago(n: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=n)


async def _seed_login(session: AsyncSession, username: str, occurred_at: datetime) -> None:
    await ingest_event(
        session,
        "user.logged_in",
        1,
        {"username": username},
        actor_id=username,
        occurred_at=occurred_at,
    )


async def test_pg_login_activity_buckets_and_windows(
    pg_analytics_session: AsyncSession, pg_refresh: Callable[[], Awaitable[None]]
) -> None:
    await _seed_login(pg_analytics_session, "a", _days_ago(1))
    await _seed_login(pg_analytics_session, "b", _days_ago(1))
    await _seed_login(pg_analytics_session, "c", _days_ago(3))
    await _seed_login(pg_analytics_session, "old", _days_ago(40))
    await pg_refresh()

    result = await get_login_activity(pg_analytics_session, days=30)

    # Buckets by UTC day, newest first; the 40-day-old login is below the date floor.
    assert result == [
        LoginActivityPoint(day=_days_ago(1).date().isoformat(), login_count=2),
        LoginActivityPoint(day=_days_ago(3).date().isoformat(), login_count=1),
    ]


async def test_pg_only_counts_login_events(
    pg_analytics_session: AsyncSession, pg_refresh: Callable[[], Awaitable[None]]
) -> None:
    await _seed_login(pg_analytics_session, "a", _days_ago(1))
    # A non-login event on the same day must not be counted by the aggregate.
    await ingest_event(
        pg_analytics_session,
        "assessment.submitted",
        1,
        {"learner_id": "x", "competency_id": "y", "score": 1.0, "passed": True},
        actor_id="x",
        occurred_at=_days_ago(1),
    )
    await pg_refresh()

    result = await get_login_activity(pg_analytics_session, days=30)

    assert result == [LoginActivityPoint(day=_days_ago(1).date().isoformat(), login_count=1)]


async def test_pg_matches_sqlite(
    pg_analytics_session: AsyncSession,
    pg_refresh: Callable[[], Awaitable[None]],
    analytics_session: AsyncSession,
) -> None:
    # The invariant made executable: seed identical events into the real Timescale DB and
    # the in-memory SQLite DB, then assert the two dialect variants return identical results.
    seed = [("a", 1), ("b", 1), ("c", 3), ("d", 15), ("old", 40)]
    for username, days_ago in seed:
        await _seed_login(pg_analytics_session, username, _days_ago(days_ago))
        await _seed_login(analytics_session, username, _days_ago(days_ago))
    await pg_refresh()

    pg_result = await get_login_activity(pg_analytics_session, days=30)
    sqlite_result = await get_login_activity(analytics_session, days=30)

    assert pg_result == sqlite_result
