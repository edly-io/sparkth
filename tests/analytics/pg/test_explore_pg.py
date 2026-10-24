"""TimescaleDB parity tests for ``explore`` (the ``pg``-marked lane)."""

from collections.abc import Generator
from datetime import datetime, timezone
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from sparkth.core.analytics import ANALYTICS_EVENTS
from sparkth.lib.analytics import AnalyticsEventSchema, ExploreQuery, explore, ingest_event

pytestmark = pytest.mark.pg

EVENT = "test.explore_pg"


class _Flagged(AnalyticsEventSchema):
    event_type = EVENT
    version = 1

    flag: bool


@pytest.fixture(autouse=True)
def _registered() -> Generator[None, None, None]:
    ANALYTICS_EVENTS.add_item(_Flagged)
    yield
    ANALYTICS_EVENTS.remove((EVENT, 1))


def _query(**params: Any) -> ExploreQuery:
    return ExploreQuery.model_validate({"from": "2026-03-01", "to": "2026-03-31", "event_type": EVENT, **params})


async def _emit(session: AsyncSession, day: str, flag: bool) -> None:
    at = datetime.fromisoformat(day).replace(hour=12, tzinfo=timezone.utc)
    await ingest_event(session, EVENT, 1, {"flag": flag}, occurred_at=at)


async def test_group_by_boolean_reads_true_false_on_pg(pg_analytics_session: AsyncSession) -> None:
    await _emit(pg_analytics_session, "2026-03-02", True)
    await _emit(pg_analytics_session, "2026-03-02", False)
    await _emit(pg_analytics_session, "2026-03-02", False)

    result = await explore(pg_analytics_session, _query(group_by="flag"))
    filtered = await explore(pg_analytics_session, _query(filter=["flag:true"]))

    assert {t.group: t.value for t in result.totals} == {"true": 1, "false": 2}
    assert [(t.group, t.value) for t in filtered.totals] == [(None, 1)]


async def test_week_bucket_starts_monday_on_pg(pg_analytics_session: AsyncSession) -> None:
    await _emit(pg_analytics_session, "2026-03-04", True)  # Wednesday
    await _emit(pg_analytics_session, "2026-03-08", True)  # Sunday, same week
    await _emit(pg_analytics_session, "2026-03-09", True)  # Monday

    result = await explore(pg_analytics_session, _query(bucket="week"))

    assert [(p.bucket, p.value) for p in result.points] == [("2026-03-02", 2), ("2026-03-09", 1)]
