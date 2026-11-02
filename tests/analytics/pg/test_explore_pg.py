"""TimescaleDB parity tests for ``explore`` (the ``pg``-marked lane)."""

from collections.abc import Generator
from datetime import datetime, timezone
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from sparkth.core.analytics import ANALYTICS_EVENTS
from sparkth.lib.analytics import AnalyticsEventSchema, ExploreQuery, ingest_event, measure_raw_events

pytestmark = pytest.mark.pg

EVENT = "test.explore_pg"


class _Flagged(AnalyticsEventSchema):
    event_type = EVENT
    version = 1

    flag: bool


SIZED = "test.sized_pg"


class _SizedV1(AnalyticsEventSchema):
    event_type = SIZED
    version = 1

    size: str
    flag: str


class _SizedV2(AnalyticsEventSchema):
    event_type = SIZED
    version = 2

    size: int
    flag: bool


@pytest.fixture(autouse=True)
def _registered() -> Generator[None, None, None]:
    for schema in (_Flagged, _SizedV1, _SizedV2):
        ANALYTICS_EVENTS.add_item(schema)
    yield
    for schema in (_Flagged, _SizedV1, _SizedV2):
        ANALYTICS_EVENTS.remove((schema.event_type, schema.version))


def _query(**params: Any) -> ExploreQuery:
    return ExploreQuery.model_validate({"from": "2026-03-01", "to": "2026-03-31", "event_type": EVENT, **params})


async def _emit(session: AsyncSession, day: str, flag: bool) -> None:
    at = datetime.fromisoformat(day).replace(hour=12, tzinfo=timezone.utc)
    await ingest_event(session, EVENT, 1, {"flag": flag}, occurred_at=at)


async def test_group_by_boolean_reads_true_false_on_pg(pg_analytics_session: AsyncSession) -> None:
    await _emit(pg_analytics_session, "2026-03-02", True)
    await _emit(pg_analytics_session, "2026-03-02", False)
    await _emit(pg_analytics_session, "2026-03-02", False)

    result = await measure_raw_events(pg_analytics_session, _query(group_by="flag"))
    filtered = await measure_raw_events(pg_analytics_session, _query(filter=["flag:true"]))

    assert {t.group: t.value for t in result.totals} == {"true": 1, "false": 2}
    assert [(t.group, t.value) for t in filtered.totals] == [(None, 1)]


async def test_week_bucket_starts_monday_on_pg(pg_analytics_session: AsyncSession) -> None:
    await _emit(pg_analytics_session, "2026-03-04", True)  # Wednesday
    await _emit(pg_analytics_session, "2026-03-08", True)  # Sunday, same week
    await _emit(pg_analytics_session, "2026-03-09", True)  # Monday

    result = await measure_raw_events(pg_analytics_session, _query(bucket="week"))

    assert [(p.bucket, p.value) for p in result.points] == [("2026-03-02", 2), ("2026-03-09", 1)]


async def test_typed_filters_skip_a_version_that_stored_text_on_pg(pg_analytics_session: AsyncSession) -> None:
    at = datetime.fromisoformat("2026-03-02").replace(hour=12, tzinfo=timezone.utc)
    await ingest_event(pg_analytics_session, SIZED, 1, {"size": "abc", "flag": "abc"}, occurred_at=at)
    await ingest_event(pg_analytics_session, SIZED, 2, {"size": 5, "flag": True}, occurred_at=at)

    by_size = await measure_raw_events(pg_analytics_session, _query(event_type=SIZED, filter=["size:5"]))
    by_flag = await measure_raw_events(pg_analytics_session, _query(event_type=SIZED, filter=["flag:true"]))
    grouped = await measure_raw_events(pg_analytics_session, _query(event_type=SIZED, group_by="flag"))

    assert [t.value for t in by_size.totals] == [1]
    assert [t.value for t in by_flag.totals] == [1]
    assert {t.group: t.value for t in grouped.totals} == {None: 1, "true": 1}
