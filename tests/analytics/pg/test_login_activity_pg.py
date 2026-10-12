"""TimescaleDB-backed tests for login reads (the ``pg``-marked lane).

These exercise the production PostgreSQL path — ``get_logins`` reading the
``login_activity_daily_by_method`` continuous aggregate created by the analytics
migrations — which the SQLite suite can only imitate. They make the "both dialect
variants must stay semantically identical" invariant executable instead of eyeball-checked.
"""

from collections.abc import Awaitable, Callable
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.analytics import Bucket, LoginsPoint, get_logins, ingest_event

pytestmark = pytest.mark.pg


async def _seed_login(session: AsyncSession, username: str, occurred_at: datetime, method: str = "password") -> None:
    await ingest_event(
        session,
        "user.logged_in",
        1,
        {"method": method},
        actor_id=username,
        occurred_at=occurred_at,
    )


async def test_pg_logins_only_count_login_events(
    pg_analytics_session: AsyncSession, pg_refresh: Callable[[], Awaitable[None]]
) -> None:
    await _seed_login(pg_analytics_session, "a", _at("2026-03-02"))
    # A non-login event on the same day must not be counted by the aggregate.
    await ingest_event(
        pg_analytics_session,
        "assessment.submitted",
        1,
        {"learner_id": "x", "competency_id": "y", "score": 1.0, "passed": True},
        actor_id="x",
        occurred_at=_at("2026-03-02"),
    )
    await pg_refresh()

    result = await get_logins(pg_analytics_session, date(2026, 3, 1), date(2026, 3, 31), Bucket.day)

    assert result == [LoginsPoint(bucket="2026-03-02", method="password", login_count=1)]


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


async def test_pg_login_activity_daily_is_dropped(pg_analytics_session: AsyncSession) -> None:
    rows = await pg_analytics_session.execute(
        text(
            "SELECT view_name FROM timescaledb_information.continuous_aggregates"
            " WHERE view_name = 'login_activity_daily'"
        )
    )
    assert rows.scalars().all() == []
