"""Tests for the period summary: ``summarize`` and ``GET /api/v1/analytics/summary``."""

from datetime import date, datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession as SQLAlchemyAsyncSession
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User
from sparkth.lib.analytics import (
    SUMMARY_FIGURES,
    SummaryCount,
    SummaryFigure,
    ingest_event,
    register_summary_figure,
    summarize,
)
from sparkth.lib.auth import get_current_user
from sparkth.lib.plugins import SparkthPlugin
from sparkth.lib.testing import AddTranslation, grant_global_permission

URL = "/api/v1/analytics/summary"
CORE = ("logins", "active_users", "signups")


def _at(day: str, hour: int = 12, minute: int = 0) -> datetime:
    return datetime.fromisoformat(day).replace(hour=hour, minute=minute, tzinfo=timezone.utc)


async def _login(session: SQLAlchemyAsyncSession, actor: str | None, at: datetime) -> None:
    await ingest_event(session, "user.logged_in", 1, {"method": "password"}, actor_id=actor, occurred_at=at)


async def _signup(session: SQLAlchemyAsyncSession, actor: str, at: datetime) -> None:
    await ingest_event(session, "user.registered", 1, {"method": "password"}, actor_id=actor, occurred_at=at)


def _core(rows: list[SummaryCount]) -> dict[str, tuple[int, int]]:
    return {r.key: (r.current, r.previous) for r in rows if r.key in CORE}


async def test_summarize_counts_the_period_and_the_equal_length_one_before(
    analytics_session: SQLAlchemyAsyncSession,
) -> None:
    # Period 2026-03-11..2026-03-20 (10 days); previous 2026-03-01..2026-03-10.
    await _login(analytics_session, "1", _at("2026-03-11", 0))  # first instant: in
    await _login(analytics_session, "1", _at("2026-03-20", 23, 59))  # last day: in
    await _login(analytics_session, "2", _at("2026-03-21", 0))  # day after: out
    await _login(analytics_session, "3", _at("2026-03-10"))  # previous: last day
    await _login(analytics_session, "6", _at("2026-03-01", 0))  # previous: first instant
    await _login(analytics_session, "4", _at("2026-02-28"))  # before previous: out
    await _signup(analytics_session, "5", _at("2026-03-12"))

    rows = await summarize(analytics_session, date(2026, 3, 11), date(2026, 3, 20))

    assert _core(rows) == {"logins": (2, 2), "active_users": (2, 2), "signups": (1, 0)}


async def test_active_users_are_distinct_actors_across_event_types(analytics_session: SQLAlchemyAsyncSession) -> None:
    await _login(analytics_session, "1", _at("2026-03-02"))
    await _signup(analytics_session, "1", _at("2026-03-03"))
    await _signup(analytics_session, "2", _at("2026-03-03"))
    await _login(analytics_session, None, _at("2026-03-03"))  # no actor: never counted

    rows = await summarize(analytics_session, date(2026, 3, 1), date(2026, 3, 31))

    assert _core(rows)["active_users"] == (2, 0)


async def test_a_single_day_range_compares_with_the_day_before(analytics_session: SQLAlchemyAsyncSession) -> None:
    await _login(analytics_session, "1", _at("2026-03-01"))
    await _login(analytics_session, "1", _at("2026-02-28"))

    rows = await summarize(analytics_session, date(2026, 3, 1), date(2026, 3, 1))

    assert _core(rows)["logins"] == (1, 1)


async def test_figures_come_in_order_then_key_with_their_view(analytics_session: SQLAlchemyAsyncSession) -> None:
    rows = await summarize(analytics_session, date(2026, 3, 1), date(2026, 3, 31))

    core = [r for r in rows if r.key in CORE]
    assert [(r.key, r.label, r.view, r.plugin) for r in core] == [
        ("logins", "Logins", "logins", None),
        ("active_users", "Active users", None, None),
        ("signups", "Signups", None, None),
    ]


async def _seven(_session: SQLAlchemyAsyncSession, _from: date, _to: date) -> int:
    return 7


def test_registering_an_equal_figure_twice_is_a_no_op_and_a_clash_raises() -> None:
    plugin = SparkthPlugin("summarytest")
    figure = SummaryFigure("summarytest.things", "Things", _seven)
    try:
        register_summary_figure(plugin, figure)
        register_summary_figure(plugin, figure)  # the plugin built again
        assert SUMMARY_FIGURES.get("summarytest.things") == SummaryFigure(
            "summarytest.things", "Things", _seven, plugin="summarytest"
        )
        with pytest.raises(ValueError):
            register_summary_figure(plugin, SummaryFigure("summarytest.things", "Other", _seven))
    finally:
        SUMMARY_FIGURES.remove("summarytest.things")


def _login_as(user: User) -> None:
    from sparkth.main import app

    async def override() -> User:
        return user

    app.dependency_overrides[get_current_user] = override


async def _permitted_reader(session: AsyncSession) -> None:
    user = User(id=1, name="Reader", username="reader", email="r@example.com", hashed_password="x")
    session.add(user)
    await session.flush()
    await grant_global_permission(session, 1, "analytics.read")
    await session.commit()
    _login_as(user)


async def test_summary_endpoint_returns_every_figure_for_a_permitted_user(
    client: AsyncClient, session: AsyncSession, analytics_session: SQLAlchemyAsyncSession
) -> None:
    await _permitted_reader(session)
    await _login(analytics_session, "1", _at("2026-03-02"))

    response = await client.get(URL, params={"from": "2026-03-01", "to": "2026-03-31"})

    assert response.status_code == 200
    logins = next(f for f in response.json() if f["key"] == "logins")
    assert logins == {
        "key": "logins",
        "label": "Logins",
        "view": "logins",
        "plugin": None,
        "current": 1,
        "previous": 0,
    }


async def test_summary_labels_follow_the_request_language(
    client: AsyncClient,
    session: AsyncSession,
    analytics_session: SQLAlchemyAsyncSession,
    translation_catalog: AddTranslation,
) -> None:
    await _permitted_reader(session)
    translation_catalog("Logins", "Inicios de sesión")

    response = await client.get(
        URL, params={"from": "2026-03-01", "to": "2026-03-31"}, headers={"Accept-Language": "es"}
    )

    assert next(f for f in response.json() if f["key"] == "logins")["label"] == "Inicios de sesión"


@pytest.mark.parametrize(
    "params",
    [{"from": "2026-03-10", "to": "2026-03-09"}, {"from": "2025-01-01", "to": "2026-01-02"}, {"to": "2026-03-31"}],
    ids=["from-after-to", "span-367-days", "missing-from"],
)
async def test_summary_endpoint_rejects_invalid_ranges(
    client: AsyncClient, session: AsyncSession, analytics_session: SQLAlchemyAsyncSession, params: dict[str, str]
) -> None:
    await _permitted_reader(session)
    assert (await client.get(URL, params=params)).status_code == 422


async def test_summary_endpoint_forbidden_without_permission(
    client: AsyncClient, session: AsyncSession, analytics_session: SQLAlchemyAsyncSession
) -> None:
    user = User(id=2, name="Plain", username="plain", email="p@example.com", hashed_password="x")
    session.add(user)
    await session.commit()
    _login_as(user)
    assert (await client.get(URL, params={"from": "2026-03-01", "to": "2026-03-31"})).status_code == 403


async def test_summary_endpoint_requires_authentication(client: AsyncClient) -> None:
    assert (await client.get(URL, params={"from": "2026-03-01", "to": "2026-03-31"})).status_code == 401
