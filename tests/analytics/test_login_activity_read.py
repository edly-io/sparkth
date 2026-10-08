from datetime import date, datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.analytics.reads import _PG_SQL, get_login_activity
from sparkth.core.models.user import User
from sparkth.core.permissions.models import Role, RoleAssignment, RolePermission
from sparkth.lib.analytics import Bucket, LoginActivityPoint, LoginsPoint, get_logins, ingest_event
from sparkth.lib.auth import get_current_user

URL = "/api/v1/analytics/login-activity"
LOGINS_URL = "/api/v1/analytics/logins"


def _days_ago(n: int) -> datetime:
    # The read query is a calendar window relative to "now", so seed data relative
    # to the wall clock rather than at fixed dates (which would fall out of the
    # window as real time advances).
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


def test_pg_query_renders_day_label_in_utc() -> None:
    assert "to_char(day AT TIME ZONE 'UTC'" in _PG_SQL.text


def test_pg_query_windows_on_utc_dates() -> None:
    assert "day::date" not in _PG_SQL.text
    assert "(day AT TIME ZONE 'UTC')::date" in _PG_SQL.text
    assert "(now() AT TIME ZONE 'UTC')::date" in _PG_SQL.text


async def test_get_login_activity_buckets_logins_by_day(analytics_session: AsyncSession) -> None:
    older = _days_ago(2)
    newer = _days_ago(1)
    await _seed_login(analytics_session, "a", older)
    await _seed_login(analytics_session, "b", newer)
    await _seed_login(analytics_session, "c", newer)
    # A non-login event on the newer day must NOT be counted.
    await ingest_event(
        analytics_session,
        "assessment.submitted",
        1,
        {"learner_id": "x", "competency_id": "y", "score": 1.0, "passed": True},
        actor_id="x",
        occurred_at=newer,
    )

    result = await get_login_activity(analytics_session, days=30)

    assert result == [
        LoginActivityPoint(day=newer.date().isoformat(), login_count=2),
        LoginActivityPoint(day=older.date().isoformat(), login_count=1),
    ]


async def test_get_login_activity_excludes_logins_outside_window(analytics_session: AsyncSession) -> None:
    inside = _days_ago(5)
    outside = _days_ago(40)
    await _seed_login(analytics_session, "recent", inside)
    await _seed_login(analytics_session, "old", outside)

    result = await get_login_activity(analytics_session, days=30)

    # Only the login within the last 30 calendar days is returned; the 40-day-old
    # login is below the date floor even though it fits within the row cap.
    assert [p.day for p in result] == [inside.date().isoformat()]


async def test_get_login_activity_respects_days_window(analytics_session: AsyncSession) -> None:
    for day in (1, 2, 3):
        await _seed_login(analytics_session, f"u{day}", _days_ago(day))

    result = await get_login_activity(analytics_session, days=2)

    # days=2 windows to the last two calendar days; the 3-day-old login is excluded.
    assert [p.day for p in result] == [_days_ago(1).date().isoformat(), _days_ago(2).date().isoformat()]


async def _grant_analytics_read(session: AsyncSession, user_id: int) -> None:
    role = Role(name="analytics-reader")
    session.add(role)
    await session.flush()
    assert role.id is not None
    session.add(RolePermission(role_id=role.id, permission="analytics.read"))
    session.add(RoleAssignment(user_id=user_id, role_id=role.id, scope="global", scope_object_id=None))
    await session.flush()


def _login_as(client: AsyncClient, user: User) -> None:
    from sparkth.main import app

    async def override() -> User:
        return user

    app.dependency_overrides[get_current_user] = override


async def test_login_activity_endpoint_returns_rollup_for_permitted_user(
    client: AsyncClient, session: AsyncSession, analytics_session: AsyncSession
) -> None:
    user = User(id=1, name="Reader", username="reader", email="r@example.com", hashed_password="x")
    session.add(user)
    await session.flush()
    await _grant_analytics_read(session, 1)
    await session.commit()
    _login_as(client, user)

    day = _days_ago(1)
    await ingest_event(
        analytics_session,
        "user.logged_in",
        1,
        {"method": "password"},
        actor_id="reader",
        occurred_at=day,
    )

    response = await client.get(URL, params={"days": 30})
    assert response.status_code == 200
    assert response.json() == [{"day": day.date().isoformat(), "login_count": 1}]


async def test_login_activity_endpoint_forbidden_without_permission(
    client: AsyncClient, session: AsyncSession, analytics_session: AsyncSession
) -> None:
    user = User(id=2, name="Plain", username="plain", email="p@example.com", hashed_password="x")
    session.add(user)
    await session.commit()
    _login_as(client, user)

    response = await client.get(URL, params={"days": 30})
    assert response.status_code == 403


async def test_login_activity_endpoint_requires_authentication(client: AsyncClient) -> None:
    # Missing credentials are a 401 (not a 403): FastAPI 0.140 corrected the
    # security dependencies to answer per RFC 9110 with WWW-Authenticate.
    response = await client.get(URL, params={"days": 30})
    assert response.status_code == 401


def _at(day: str, hour: int = 12) -> datetime:
    return datetime.fromisoformat(day).replace(hour=hour, tzinfo=timezone.utc)


async def test_get_logins_buckets_by_day_and_method(analytics_session: AsyncSession) -> None:
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


async def test_get_logins_range_is_inclusive_on_both_ends(analytics_session: AsyncSession) -> None:
    await _seed_login(analytics_session, "before", _at("2026-02-28", 23))
    await _seed_login(analytics_session, "first", _at("2026-03-01", 0))
    await _seed_login(analytics_session, "last", _at("2026-03-10", 23))
    await _seed_login(analytics_session, "after", _at("2026-03-11", 0))

    result = await get_logins(analytics_session, date(2026, 3, 1), date(2026, 3, 10), Bucket.day)

    assert [p.bucket for p in result] == ["2026-03-01", "2026-03-10"]


async def test_get_logins_week_starts_monday_across_a_year_boundary(analytics_session: AsyncSession) -> None:
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


async def test_get_logins_week_bucket_filters_on_the_day(analytics_session: AsyncSession) -> None:
    # The range cuts mid-week: only days inside it count toward the Monday bucket.
    await _seed_login(analytics_session, "mon", _at("2025-12-29"))
    await _seed_login(analytics_session, "thu", _at("2026-01-01"))

    result = await get_logins(analytics_session, date(2025, 12, 31), date(2026, 1, 31), Bucket.week)

    assert result == [LoginsPoint(bucket="2025-12-29", method="password", login_count=1)]


async def test_get_logins_month_buckets_on_the_first(analytics_session: AsyncSession) -> None:
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
    await _grant_analytics_read(session, 1)
    await session.commit()
    _login_as(client, user)


async def test_logins_endpoint_returns_points_for_permitted_user(
    client: AsyncClient, session: AsyncSession, analytics_session: AsyncSession
) -> None:
    await _permitted_reader(client, session)
    await _seed_login(analytics_session, "reader", _at("2026-03-02"), method="google")

    response = await client.get(LOGINS_URL, params={"from": "2026-03-01", "to": "2026-03-31", "bucket": "week"})

    assert response.status_code == 200
    assert response.json() == [{"bucket": "2026-03-02", "method": "google", "login_count": 1}]


async def test_logins_endpoint_defaults_to_day_buckets(
    client: AsyncClient, session: AsyncSession, analytics_session: AsyncSession
) -> None:
    await _permitted_reader(client, session)
    await _seed_login(analytics_session, "reader", _at("2026-03-04"))

    response = await client.get(LOGINS_URL, params={"from": "2026-03-01", "to": "2026-03-31"})

    assert response.status_code == 200
    assert response.json() == [{"bucket": "2026-03-04", "method": "password", "login_count": 1}]


async def test_logins_endpoint_accepts_a_366_day_span(
    client: AsyncClient, session: AsyncSession, analytics_session: AsyncSession
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
    client: AsyncClient, session: AsyncSession, analytics_session: AsyncSession, params: dict[str, str]
) -> None:
    await _permitted_reader(client, session)

    response = await client.get(LOGINS_URL, params=params)

    assert response.status_code == 422


async def test_logins_endpoint_forbidden_without_permission(
    client: AsyncClient, session: AsyncSession, analytics_session: AsyncSession
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
