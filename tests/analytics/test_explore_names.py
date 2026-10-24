"""Tests for actor names in ``GET /api/v1/analytics/query``."""

from collections.abc import Generator
from datetime import datetime, timezone
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession as SQLAlchemyAsyncSession
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.analytics import ANALYTICS_EVENTS
from sparkth.core.models.user import User
from sparkth.lib.analytics import AnalyticsEventSchema, ingest_event
from sparkth.lib.auth import get_current_user
from sparkth.lib.testing import grant_global_permission

URL = "/api/v1/analytics/query"
EVENT = "test.explore_names"


class _Named(AnalyticsEventSchema):
    event_type = EVENT
    version = 1

    outcome: str
    label: str


@pytest.fixture(autouse=True)
def _registered() -> Generator[None, None, None]:
    ANALYTICS_EVENTS.add_item(_Named)
    yield
    ANALYTICS_EVENTS.remove((_Named.event_type, _Named.version))


def _params(**params: Any) -> dict[str, Any]:
    return {"from": "2026-03-01", "to": "2026-03-31", "event_type": EVENT, "group_by": "actor", **params}


async def _setup(session: AsyncSession, analytics: SQLAlchemyAsyncSession, *permissions: str) -> None:
    reader = User(id=1, name="Reader", username="reader", email="r@example.com", hashed_password="x")
    other = User(id=2, name="Other", username="other", email="o@example.com", hashed_password="x")
    session.add_all([reader, other])
    await session.flush()
    for permission in permissions:
        await grant_global_permission(session, 1, permission)
    await session.commit()

    from sparkth.main import app

    async def override() -> User:
        return reader

    app.dependency_overrides[get_current_user] = override
    for actor in ("1", "2", "999", "abc"):
        await ingest_event(
            analytics,
            EVENT,
            1,
            {"outcome": "succeeded", "label": "1"},
            actor_id=actor,
            occurred_at=datetime(2026, 3, 2, 12, tzinfo=timezone.utc),
        )


async def test_actor_names_present_with_user_read(
    client: AsyncClient, session: AsyncSession, analytics_session: SQLAlchemyAsyncSession
) -> None:
    await _setup(session, analytics_session, "analytics.read", "user.read")

    response = await client.get(URL, params=_params(group_by="actor", **{"filter": "outcome:succeeded"}))

    assert response.status_code == 200
    assert response.json()["actor_names"] == {"1": "reader", "2": "other"}


async def test_actor_names_absent_without_user_read(
    client: AsyncClient, session: AsyncSession, analytics_session: SQLAlchemyAsyncSession
) -> None:
    await _setup(session, analytics_session, "analytics.read")

    response = await client.get(URL, params=_params())

    assert response.status_code == 200
    assert response.json()["actor_names"] == {}


async def test_actor_names_skip_unknown_and_non_numeric_ids(
    client: AsyncClient, session: AsyncSession, analytics_session: SQLAlchemyAsyncSession
) -> None:
    await _setup(session, analytics_session, "analytics.read", "user.read")

    response = await client.get(URL, params=_params())

    assert response.status_code == 200
    names = response.json()["actor_names"]
    assert "999" not in names and "abc" not in names


async def test_actor_names_only_for_group_by_actor(
    client: AsyncClient, session: AsyncSession, analytics_session: SQLAlchemyAsyncSession
) -> None:
    await _setup(session, analytics_session, "analytics.read", "user.read")

    response = await client.get(URL, params=_params(group_by="label"))

    assert response.status_code == 200
    assert response.json()["actor_names"] == {}
