"""Tests for the logins read: ``get_logins`` and ``GET /api/v1/analytics/logins``."""

from datetime import date, datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession as SQLAlchemyAsyncSession
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User
from sparkth.lib.analytics import (
    SQLITE_BUCKET,
    Bucket,
    LoginsPoint,
    RangeQuery,
    get_logins,
    ingest_event,
    read_bucketed,
)
from sparkth.lib.auth import get_current_user
from sparkth.lib.testing import grant_global_permission

URL = "/api/v1/analytics/login-activity"
LOGINS_URL = "/api/v1/analytics/logins"


async def _seed_login(
    session: SQLAlchemyAsyncSession, username: str, occurred_at: datetime, method: str = "password"
) -> None:
    await ingest_event(
        session,
        "user.logged_in",
        1,
        {"method": method},
        actor_id=username,
        occurred_at=occurred_at,
    )


def _login_as(client: AsyncClient, user: User) -> None:
    from sparkth.main import app

    async def override() -> User:
        return user

    app.dependency_overrides[get_current_user] = override


def _at(day: str, hour: int = 12) -> datetime:
    return datetime.fromisoformat(day).replace(hour=hour, tzinfo=timezone.utc)


async def test_get_logins_buckets_by_day_and_method(analytics_session: SQLAlchemyAsyncSession) -> None:
    await _seed_login(analytics_session, "a", _at("2026-03-02", 0))
    await _seed_login(analytics_session, "b", _at("2026-03-02", 23), method="google")
    await _seed_login(analytics_session, "c", _at("2026-03-02"), method="google")
    await _seed_login(analytics_session, "d", _at("2026-03-04"))
    await ingest_event(
        analytics_session,
        "assessment.submitted",
        1,
        {"learner_id": "x", "competency_id": "y", "score": 1.0, "passed": True},
        actor_id="x",
        occurred_at=_at("2026-03-02"),
    )

    result = await get_logins(analytics_session, date(2026, 3, 1), date(2026, 3, 31), Bucket.day)

    assert result == [
        LoginsPoint(bucket="2026-03-02", method="google", login_count=2),
        LoginsPoint(bucket="2026-03-02", method="password", login_count=1),
        LoginsPoint(bucket="2026-03-04", method="password", login_count=1),
    ]


async def test_get_logins_range_is_inclusive_on_both_ends(analytics_session: SQLAlchemyAsyncSession) -> None:
    await _seed_login(analytics_session, "before", _at("2026-02-28", 23))
    await _seed_login(analytics_session, "first", _at("2026-03-01", 0))
    await _seed_login(analytics_session, "last", _at("2026-03-10", 23))
    await _seed_login(analytics_session, "after", _at("2026-03-11", 0))

    result = await get_logins(analytics_session, date(2026, 3, 1), date(2026, 3, 10), Bucket.day)

    assert [p.bucket for p in result] == ["2026-03-01", "2026-03-10"]


async def test_get_logins_week_starts_monday_across_a_year_boundary(analytics_session: SQLAlchemyAsyncSession) -> None:
    # 2025-12-29 is a Monday; that week runs to Sunday 2026-01-04.
    await _seed_login(analytics_session, "mon", _at("2025-12-29"))
    await _seed_login(analytics_session, "thu", _at("2026-01-01"))
    await _seed_login(analytics_session, "sun", _at("2026-01-04"))
    await _seed_login(analytics_session, "next", _at("2026-01-05"))

    result = await get_logins(analytics_session, date(2025, 12, 1), date(2026, 1, 31), Bucket.week)

    assert result == [
        LoginsPoint(bucket="2025-12-29", method="password", login_count=3),
        LoginsPoint(bucket="2026-01-05", method="password", login_count=1),
    ]


async def test_get_logins_week_bucket_filters_on_the_day(analytics_session: SQLAlchemyAsyncSession) -> None:
    # The range cuts mid-week: only days inside it count toward the Monday bucket.
    await _seed_login(analytics_session, "mon", _at("2025-12-29"))
    await _seed_login(analytics_session, "thu", _at("2026-01-01"))

    result = await get_logins(analytics_session, date(2025, 12, 31), date(2026, 1, 31), Bucket.week)

    assert result == [LoginsPoint(bucket="2025-12-29", method="password", login_count=1)]


async def test_get_logins_month_buckets_on_the_first(analytics_session: SQLAlchemyAsyncSession) -> None:
    await _seed_login(analytics_session, "a", _at("2026-01-15"))
    await _seed_login(analytics_session, "b", _at("2026-01-31", 23), method="google")
    await _seed_login(analytics_session, "c", _at("2026-02-01", 0))

    result = await get_logins(analytics_session, date(2026, 1, 1), date(2026, 2, 28), Bucket.month)

    assert result == [
        LoginsPoint(bucket="2026-01-01", method="google", login_count=1),
        LoginsPoint(bucket="2026-01-01", method="password", login_count=1),
        LoginsPoint(bucket="2026-02-01", method="password", login_count=1),
    ]


async def _permitted_reader(client: AsyncClient, session: AsyncSession) -> None:
    user = User(id=1, name="Reader", username="reader", email="r@example.com", hashed_password="x")
    session.add(user)
    await session.flush()
    await grant_global_permission(session, 1, "analytics.read")
    await session.commit()
    _login_as(client, user)


async def test_logins_endpoint_returns_points_for_permitted_user(
    client: AsyncClient, session: AsyncSession, analytics_session: SQLAlchemyAsyncSession
) -> None:
    await _permitted_reader(client, session)
    await _seed_login(analytics_session, "reader", _at("2026-03-02"), method="google")

    response = await client.get(LOGINS_URL, params={"from": "2026-03-01", "to": "2026-03-31", "bucket": "week"})

    assert response.status_code == 200
    assert response.json() == [{"bucket": "2026-03-02", "method": "google", "login_count": 1}]


async def test_logins_endpoint_defaults_to_day_buckets(
    client: AsyncClient, session: AsyncSession, analytics_session: SQLAlchemyAsyncSession
) -> None:
    await _permitted_reader(client, session)
    await _seed_login(analytics_session, "reader", _at("2026-03-04"))

    response = await client.get(LOGINS_URL, params={"from": "2026-03-01", "to": "2026-03-31"})

    assert response.status_code == 200
    assert response.json() == [{"bucket": "2026-03-04", "method": "password", "login_count": 1}]


async def test_logins_endpoint_accepts_a_366_day_span(
    client: AsyncClient, session: AsyncSession, analytics_session: SQLAlchemyAsyncSession
) -> None:
    await _permitted_reader(client, session)

    response = await client.get(LOGINS_URL, params={"from": "2024-01-01", "to": "2024-12-31"})

    assert response.status_code == 200


@pytest.mark.parametrize(
    "params",
    [
        {"from": "2026-03-10", "to": "2026-03-09"},
        {"from": "2025-01-01", "to": "2026-01-02"},
        {"from": "2026-03-01", "to": "2026-03-31", "bucket": "year"},
        {"to": "2026-03-31"},
    ],
    ids=["from-after-to", "span-367-days", "unknown-bucket", "missing-from"],
)
async def test_logins_endpoint_rejects_invalid_query(
    client: AsyncClient, session: AsyncSession, analytics_session: SQLAlchemyAsyncSession, params: dict[str, str]
) -> None:
    await _permitted_reader(client, session)

    response = await client.get(LOGINS_URL, params=params)

    assert response.status_code == 422


async def test_logins_endpoint_forbidden_without_permission(
    client: AsyncClient, session: AsyncSession, analytics_session: SQLAlchemyAsyncSession
) -> None:
    user = User(id=2, name="Plain", username="plain", email="p@example.com", hashed_password="x")
    session.add(user)
    await session.commit()
    _login_as(client, user)

    response = await client.get(LOGINS_URL, params={"from": "2026-03-01", "to": "2026-03-31"})
    assert response.status_code == 403


async def test_logins_endpoint_requires_authentication(client: AsyncClient) -> None:
    response = await client.get(LOGINS_URL, params={"from": "2026-03-01", "to": "2026-03-31"})
    assert response.status_code == 401


async def test_login_activity_endpoint_is_gone(
    client: AsyncClient, session: AsyncSession, analytics_session: SQLAlchemyAsyncSession
) -> None:
    user = User(id=3, name="Reader", username="reader3", email="r3@example.com", hashed_password="x")
    session.add(user)
    await session.flush()
    await grant_global_permission(session, 3, "analytics.read")
    await session.commit()
    _login_as(client, user)

    response = await client.get(URL, params={"days": 30})
    assert response.status_code == 404


async def test_read_bucketed_binds_the_range_and_returns_rows(analytics_session: SQLAlchemyAsyncSession) -> None:
    await _seed_login(analytics_session, "a", _at("2026-03-02"))
    await _seed_login(analytics_session, "b", _at("2026-03-02"))
    await _seed_login(analytics_session, "c", _at("2026-04-02"))
    sqlite_sql = {
        b: text(
            f"SELECT {SQLITE_BUCKET[b]} AS bucket, count(*) AS n FROM raw_events "
            "WHERE date(occurred_at) BETWEEN :from_ AND :to GROUP BY 1"
        )
        for b in Bucket
    }

    rows = await read_bucketed(analytics_session, {}, sqlite_sql, date(2026, 3, 1), date(2026, 3, 31), Bucket.day)

    assert [dict(r) for r in rows] == [{"bucket": "2026-03-02", "n": 2}]


def test_range_query_rejects_inverted_and_overlong_ranges() -> None:
    def parse(start: str, end: str) -> RangeQuery:
        return RangeQuery.model_validate({"from": start, "to": end})

    with pytest.raises(ValueError):
        parse("2026-03-02", "2026-03-01")
    with pytest.raises(ValueError):
        parse("2026-01-01", "2027-01-02")  # 367 days
    assert parse("2026-01-01", "2027-01-01").bucket == Bucket.day  # 366 days
