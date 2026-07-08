from datetime import datetime, timedelta, timezone

from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.analytics.reads import _PG_SQL, LoginActivityPoint, get_login_activity
from sparkth.core.models.user import User
from sparkth.core.permissions.models import Role, RoleAssignment, RolePermission
from sparkth.lib.analytics import ingest_event
from sparkth.lib.auth import get_current_user

URL = "/api/v1/analytics/login-activity"


def _days_ago(n: int) -> datetime:
    # The read query is a calendar window relative to "now", so seed data relative
    # to the wall clock rather than at fixed dates (which would fall out of the
    # window as real time advances).
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
        {"username": "reader"},
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
    response = await client.get(URL, params={"days": 30})
    assert response.status_code == 403
