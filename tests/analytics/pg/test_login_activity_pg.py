"""TimescaleDB-backed tests for login-activity reads (the ``pg``-marked lane).

These exercise the production PostgreSQL path — ``_PG_SQL`` reading the
``login_activity_daily`` continuous aggregate and ``get_logins`` reading
``login_activity_daily_by_method``, both created by the analytics migrations —
which the SQLite suite can only imitate. They make the "both dialect variants must stay
semantically identical" invariant executable instead of eyeball-checked.
"""

from collections.abc import Awaitable, Callable
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.analytics import Bucket, LoginActivityPoint, LoginsPoint, get_login_activity, get_logins, ingest_event

pytestmark = pytest.mark.pg


def _days_ago(n: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=n)


async def _seed_login(session: AsyncSession, username: str, occurred_at: datetime, method: str = "password") -> None:
    await ingest_event(
        session,
        "user.logged_in",
        1,
        {"method": method},
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


def _at(day: str, hour: int = 12) -> datetime:
    return datetime.fromisoformat(day).replace(hour=hour, tzinfo=timezone.utc)


async def test_pg_login_activity_by_method_cagg_exists(pg_analytics_session: AsyncSession) -> None:
    rows = await pg_analytics_session.execute(
        text(
            "SELECT view_name FROM timescaledb_information.continuous_aggregates"
            " WHERE view_name = 'login_activity_daily_by_method'"
        )
    )
    assert rows.scalars().all() == ["login_activity_daily_by_method"]


async def test_pg_logins_bucket_by_method(
    pg_analytics_session: AsyncSession, pg_refresh: Callable[[], Awaitable[None]]
) -> None:
    await _seed_login(pg_analytics_session, "a", _at("2025-12-29"))
    await _seed_login(pg_analytics_session, "b", _at("2026-01-04", 23), method="google")
    await _seed_login(pg_analytics_session, "c", _at("2026-01-05", 0))
    await pg_refresh()

    result = await get_logins(pg_analytics_session, date(2025, 12, 1), date(2026, 1, 31), Bucket.week)

    assert result == [
        LoginsPoint(bucket="2025-12-29", method="google", login_count=1),
        LoginsPoint(bucket="2025-12-29", method="password", login_count=1),
        LoginsPoint(bucket="2026-01-05", method="password", login_count=1),
    ]


@pytest.mark.parametrize("bucket", list(Bucket))
async def test_pg_logins_match_sqlite(
    pg_analytics_session: AsyncSession,
    pg_refresh: Callable[[], Awaitable[None]],
    analytics_session: AsyncSession,
    bucket: Bucket,
) -> None:
    seed = [
        ("a", _at("2025-11-30", 23), "password"),
        ("b", _at("2025-12-01", 0), "google"),
        ("c", _at("2025-12-29"), "password"),
        ("d", _at("2026-01-01"), "google"),
        ("e", _at("2026-01-04", 23), "password"),
        ("f", _at("2026-01-31", 23), "password"),
        ("g", _at("2026-02-01", 0), "google"),
    ]
    for username, occurred_at, method in seed:
        await _seed_login(pg_analytics_session, username, occurred_at, method)
        await _seed_login(analytics_session, username, occurred_at, method)
    await pg_refresh()

    pg_result = await get_logins(pg_analytics_session, date(2025, 12, 1), date(2026, 1, 31), bucket)
    sqlite_result = await get_logins(analytics_session, date(2025, 12, 1), date(2026, 1, 31), bucket)

    assert pg_result == sqlite_result
    assert pg_result
