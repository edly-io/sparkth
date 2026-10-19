"""TimescaleDB parity test for the period summary (the ``pg``-marked lane)."""

from collections.abc import Awaitable, Callable
from datetime import date, datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from sparkth.lib.analytics import ingest_event, summarize

pytestmark = pytest.mark.pg


def _at(day: str, hour: int = 12) -> datetime:
    return datetime.fromisoformat(day).replace(hour=hour, tzinfo=timezone.utc)


async def test_pg_summary_matches_sqlite_on_edges_and_distinct_actors(
    pg_analytics_session: AsyncSession, pg_refresh: Callable[[], Awaitable[None]]
) -> None:
    s = pg_analytics_session
    await ingest_event(s, "user.logged_in", 1, {"method": "password"}, actor_id="1", occurred_at=_at("2026-03-11", 0))
    await ingest_event(s, "user.logged_in", 1, {"method": "password"}, actor_id="1", occurred_at=_at("2026-03-20", 23))
    await ingest_event(s, "user.logged_in", 1, {"method": "password"}, actor_id="2", occurred_at=_at("2026-03-21", 0))
    await ingest_event(s, "user.registered", 1, {"method": "password"}, actor_id="3", occurred_at=_at("2026-03-10"))
    await pg_refresh()

    rows = await summarize(s, date(2026, 3, 11), date(2026, 3, 20))

    core = {r.key: (r.current, r.previous) for r in rows if r.plugin is None}
    assert core == {"logins": (2, 0), "active_users": (1, 1), "signups": (0, 1)}
