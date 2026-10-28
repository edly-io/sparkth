"""Tests for the event catalog: ``event_catalog`` and ``GET /api/v1/analytics/events``."""

from collections.abc import Generator
from enum import StrEnum
from typing import Literal

import pytest
from httpx import AsyncClient
from pydantic import NonNegativeInt
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.analytics import ANALYTICS_EVENTS
from sparkth.core.models.user import User
from sparkth.lib.analytics import AnalyticsEventSchema, EventField, FilterFieldType, catalog_entry, event_catalog
from sparkth.lib.auth import get_current_user
from sparkth.lib.testing import grant_global_permission

URL = "/api/v1/analytics/events"


class _Outcome(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class _Kinds(AnalyticsEventSchema):
    event_type = "test.kinds"
    version = 1

    name: str
    outcome: _Outcome
    source: Literal["a", "b"]
    flag: bool
    count: NonNegativeInt
    reason: _Outcome | None
    score: float  # unsupported kind: omitted


class _MergedV1(AnalyticsEventSchema):
    event_type = "test.merged"
    version = 1

    x: str


class _MergedV2(AnalyticsEventSchema):
    event_type = "test.merged"
    version = 2

    x: int
    y: str


@pytest.fixture(autouse=True)
def _registered() -> Generator[None, None, None]:
    for schema in (_Kinds, _MergedV1, _MergedV2):
        ANALYTICS_EVENTS.add_item(schema)
    yield
    for schema in (_Kinds, _MergedV1, _MergedV2):
        ANALYTICS_EVENTS.remove((schema.event_type, schema.version))


def test_catalog_derives_field_kinds() -> None:
    entry = catalog_entry("test.kinds")

    assert entry is not None
    by_name = {f.name: f for f in entry.fields}
    assert set(by_name) == {"count", "flag", "name", "outcome", "reason", "source"}
    assert by_name["flag"].kind == "boolean" and by_name["count"].kind == "integer"
    assert by_name["name"].kind == "string" and by_name["name"].values is None
    assert by_name["outcome"].values == ["succeeded", "failed"]
    assert by_name["source"] == EventField(name="source", kind=FilterFieldType.enum, values=["a", "b"], nullable=False)
    assert by_name["reason"].nullable is True and by_name["reason"].kind == "enum"


def test_catalog_merges_versions_highest_kind_wins() -> None:
    entry = catalog_entry("test.merged")

    assert entry is not None
    assert {f.name: f.kind for f in entry.fields} == {"x": "integer", "y": "string"}


def test_catalog_lists_core_events_sorted() -> None:
    entries = event_catalog()

    assert [e.event_type for e in entries] == sorted(e.event_type for e in entries)
    logged_in = next(e for e in entries if e.event_type == "user.logged_in")
    assert next(f for f in logged_in.fields if f.name == "method").values == ["password", "google"]
    assert catalog_entry("nope.nothing") is None


def _login_as(user: User) -> None:
    from sparkth.main import app

    async def override() -> User:
        return user

    app.dependency_overrides[get_current_user] = override


async def test_events_endpoint_returns_catalog_for_a_permitted_user(client: AsyncClient, session: AsyncSession) -> None:
    user = User(id=1, name="Reader", username="reader", email="r@example.com", hashed_password="x")
    session.add(user)
    await session.flush()
    await grant_global_permission(session, 1, "analytics.read")
    await session.commit()
    _login_as(user)

    response = await client.get(URL)

    assert response.status_code == 200
    assert "user.logged_in" in {e["event_type"] for e in response.json()}


async def test_events_endpoint_forbidden_without_permission(client: AsyncClient, session: AsyncSession) -> None:
    user = User(id=2, name="Plain", username="plain", email="p@example.com", hashed_password="x")
    session.add(user)
    await session.commit()
    _login_as(user)

    assert (await client.get(URL)).status_code == 403


async def test_events_endpoint_requires_authentication(client: AsyncClient) -> None:
    assert (await client.get(URL)).status_code == 401
