"""Tests for raw event exploration: ``explore`` and ``GET /api/v1/analytics/query``."""

from collections.abc import Generator
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession as SQLAlchemyAsyncSession
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.analytics import ANALYTICS_EVENTS
from sparkth.core.analytics.models import raw_events
from sparkth.core.models.user import User
from sparkth.lib.analytics import (
    AnalyticsEventSchema,
    ExploreQuery,
    ExploreQueryError,
    ExploreResult,
    InvalidFilterValue,
    UngroupableExploreField,
    UnknownExploreEvent,
    UnknownExploreField,
    ingest_event,
    measure_raw_events,
)
from sparkth.lib.auth import get_current_user
from sparkth.lib.testing import grant_global_permission

URL = "/api/v1/analytics/query"
EVENT = "test.explore"


class _Outcome(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class _Explore(AnalyticsEventSchema):
    event_type = EVENT
    version = 1

    outcome: _Outcome
    flag: bool
    reason: _Outcome | None
    name: str
    size: int


class _Other(AnalyticsEventSchema):
    event_type = "test.other"
    version = 1

    name: str


@pytest.fixture(autouse=True)
def _registered() -> Generator[None, None, None]:
    for schema in (_Explore, _Other):
        ANALYTICS_EVENTS.add_item(schema)
    yield
    for schema in (_Explore, _Other):
        ANALYTICS_EVENTS.remove((schema.event_type, schema.version))


def _at(day: str, hour: int = 12) -> datetime:
    return datetime.fromisoformat(day).replace(hour=hour, tzinfo=timezone.utc)


async def _emit(
    session: SQLAlchemyAsyncSession,
    day: str,
    actor: str | None = "1",
    hour: int = 12,
    **payload: Any,
) -> None:
    body = {"outcome": "succeeded", "flag": False, "reason": None, "name": "a", "size": 1, **payload}
    await ingest_event(session, EVENT, 1, body, actor_id=actor, occurred_at=_at(day, hour))


def _query(**params: Any) -> ExploreQuery:
    return ExploreQuery.model_validate({"from": "2026-03-01", "to": "2026-03-31", "event_type": EVENT, **params})


def _points(result: ExploreResult) -> list[tuple[str, str | None, int]]:
    return [(p.bucket, p.group, p.value) for p in result.points]


async def test_counts_one_event_type_per_bucket(analytics_session: SQLAlchemyAsyncSession) -> None:
    await _emit(analytics_session, "2026-03-01", hour=0)
    await _emit(analytics_session, "2026-03-01")
    await _emit(analytics_session, "2026-03-31", hour=23)
    await _emit(analytics_session, "2026-04-01", hour=0)  # after the range
    await _emit(analytics_session, "2026-02-28", hour=23)  # before the range
    await ingest_event(analytics_session, "test.other", 1, {"name": "x"}, occurred_at=_at("2026-03-01"))

    result = await measure_raw_events(analytics_session, _query())

    assert _points(result) == [("2026-03-01", None, 2), ("2026-03-31", None, 1)]
    assert [(t.group, t.value) for t in result.totals] == [(None, 3)]
    assert result.truncated is False and result.actor_names == {}


async def test_week_and_month_buckets_start_monday_and_first(analytics_session: SQLAlchemyAsyncSession) -> None:
    await _emit(analytics_session, "2026-03-04")  # Wednesday
    await _emit(analytics_session, "2026-03-08")  # Sunday, same week
    await _emit(analytics_session, "2026-03-09")  # Monday

    week = await measure_raw_events(analytics_session, _query(bucket="week"))
    month = await measure_raw_events(analytics_session, _query(bucket="month"))

    assert _points(week) == [("2026-03-02", None, 2), ("2026-03-09", None, 1)]
    assert _points(month) == [("2026-03-01", None, 3)]


async def test_distinct_actors_counts_each_actor_once_per_bucket(analytics_session: SQLAlchemyAsyncSession) -> None:
    await _emit(analytics_session, "2026-03-02", actor="1")
    await _emit(analytics_session, "2026-03-02", actor="1")
    await _emit(analytics_session, "2026-03-02", actor="2")
    await _emit(analytics_session, "2026-03-02", actor=None)

    result = await measure_raw_events(analytics_session, _query(measure="distinct_actors"))

    assert _points(result) == [("2026-03-02", None, 2)]


async def test_filters_and_within_a_field_or_across_fields(analytics_session: SQLAlchemyAsyncSession) -> None:
    await _emit(analytics_session, "2026-03-02", outcome="failed", flag=True)
    await _emit(analytics_session, "2026-03-02", outcome="succeeded", flag=True)
    await _emit(analytics_session, "2026-03-02", outcome="failed", flag=False)
    await _emit(analytics_session, "2026-03-02", outcome="succeeded", flag=False)

    result = await measure_raw_events(
        analytics_session, _query(filter=["outcome:failed", "outcome:succeeded", "flag:true"])
    )
    narrowed = await measure_raw_events(analytics_session, _query(filter=["outcome:failed", "flag:true", "size:1"]))

    assert _points(result) == [("2026-03-02", None, 2)]
    assert _points(narrowed) == [("2026-03-02", None, 1)]


async def test_null_filter_matches_missing_and_null(analytics_session: SQLAlchemyAsyncSession) -> None:
    await _emit(analytics_session, "2026-03-02", reason=None)
    await _emit(analytics_session, "2026-03-02", reason="failed")
    await analytics_session.execute(
        raw_events.insert().values(
            occurred_at=_at("2026-03-02"), event_type=EVENT, event_version=1, payload={"name": "old"}
        )
    )
    await analytics_session.commit()

    result = await measure_raw_events(analytics_session, _query(filter=["reason:null"]))

    assert _points(result) == [("2026-03-02", None, 2)]


async def test_actor_filter(analytics_session: SQLAlchemyAsyncSession) -> None:
    await _emit(analytics_session, "2026-03-02", actor="1")
    await _emit(analytics_session, "2026-03-02", actor="2")

    result = await measure_raw_events(analytics_session, _query(actor_id="2"))

    assert _points(result) == [("2026-03-02", None, 1)]


async def test_group_by_boolean_reads_true_false(analytics_session: SQLAlchemyAsyncSession) -> None:
    await _emit(analytics_session, "2026-03-02", flag=True)
    await _emit(analytics_session, "2026-03-02", flag=False)
    await _emit(analytics_session, "2026-03-02", flag=False)

    result = await measure_raw_events(analytics_session, _query(group_by="flag"))

    assert {t.group: t.value for t in result.totals} == {"true": 1, "false": 2}
    assert _points(result) == [("2026-03-02", "false", 2), ("2026-03-02", "true", 1)]


async def test_group_by_actor(analytics_session: SQLAlchemyAsyncSession) -> None:
    await _emit(analytics_session, "2026-03-02", actor="7")
    await _emit(analytics_session, "2026-03-02", actor=None)

    result = await measure_raw_events(analytics_session, _query(group_by="actor"))

    assert _points(result) == [("2026-03-02", None, 1), ("2026-03-02", "7", 1)]


async def test_totals_are_distinct_over_the_range(analytics_session: SQLAlchemyAsyncSession) -> None:
    await _emit(analytics_session, "2026-03-02", actor="1", outcome="failed")
    await _emit(analytics_session, "2026-03-20", actor="1", outcome="failed")

    result = await measure_raw_events(analytics_session, _query(group_by="outcome", measure="distinct_actors"))

    assert _points(result) == [("2026-03-02", "failed", 1), ("2026-03-20", "failed", 1)]
    assert [(t.group, t.value) for t in result.totals] == [("failed", 1)]


async def test_keeps_top_twenty_groups_and_flags_truncation(analytics_session: SQLAlchemyAsyncSession) -> None:
    for i in range(21):
        await _emit(analytics_session, "2026-03-02", name=f"n{i:02}")
    await _emit(analytics_session, "2026-03-03", name="n20")

    result = await measure_raw_events(analytics_session, _query(group_by="name"))

    groups = [t.group for t in result.totals]
    assert len(groups) == 20 and groups[0] == "n20" and "n19" not in groups
    assert result.truncated is True
    assert {p.group for p in result.points} == set(groups)


@pytest.mark.parametrize(
    ("params", "error"),
    [
        pytest.param({"event_type": "nope.nothing"}, UnknownExploreEvent, id="UnknownExploreEvent"),
        pytest.param({"filter": ["missing:x"]}, UnknownExploreField, id="UnknownExploreField-filter"),
        pytest.param({"group_by": "missing"}, UnknownExploreField, id="UnknownExploreField-group_by"),
        pytest.param({"filter": ["outcome:maybe"]}, InvalidFilterValue, id="InvalidFilterValue-enum"),
        pytest.param({"filter": ["flag:yes"]}, InvalidFilterValue, id="InvalidFilterValue-boolean"),
        pytest.param({"filter": ["size:big"]}, InvalidFilterValue, id="InvalidFilterValue-integer"),
        pytest.param({"filter": ["size:99999999999"]}, InvalidFilterValue, id="InvalidFilterValue-above-int32"),
        pytest.param({"filter": ["size:-2147483649"]}, InvalidFilterValue, id="InvalidFilterValue-below-int32"),
        pytest.param({"group_by": "size"}, UngroupableExploreField, id="UngroupableExploreField"),
    ],
)
async def test_each_query_error_is_raised_and_served_as_422(
    params: dict[str, Any],
    error: type[ExploreQueryError],
    client: AsyncClient,
    session: AsyncSession,
    analytics_session: SQLAlchemyAsyncSession,
) -> None:
    with pytest.raises(error) as raised:
        await measure_raw_events(analytics_session, _query(**params))
    await _permitted(session)

    response = await client.get(URL, params=_params(**params))

    assert response.status_code == 422
    assert response.json()["detail"] == str(raised.value)


async def test_query_endpoint_returns_result_for_a_permitted_user(client: AsyncClient, session: AsyncSession) -> None:
    await _permitted(session)

    response = await client.get(URL, params=_params(filter=["outcome:failed", "flag:true"], group_by="actor"))

    assert response.status_code == 200
    assert response.json() == {"points": [], "totals": [], "truncated": False, "actor_names": {}}


async def test_query_endpoint_forbidden_without_permission(client: AsyncClient, session: AsyncSession) -> None:
    user = User(id=2, name="Plain", username="plain", email="p@example.com", hashed_password="x")
    session.add(user)
    await session.commit()
    _login_as(user)

    assert (await client.get(URL, params=_params())).status_code == 403


async def test_query_endpoint_requires_authentication(client: AsyncClient) -> None:
    assert (await client.get(URL, params=_params())).status_code == 401


def _params(**params: Any) -> dict[str, Any]:
    return {"from": "2026-03-01", "to": "2026-03-31", "event_type": EVENT, **params}


def _login_as(user: User) -> None:
    from sparkth.main import app

    async def override() -> User:
        return user

    app.dependency_overrides[get_current_user] = override


async def _permitted(session: AsyncSession) -> None:
    user = User(id=1, name="Reader", username="reader", email="r@example.com", hashed_password="x")
    session.add(user)
    await session.flush()
    await grant_global_permission(session, 1, "analytics.read")
    await session.commit()
    _login_as(user)
