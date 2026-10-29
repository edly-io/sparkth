"""TimescaleDB-backed tests for the compose activity read (the ``pg``-marked lane).

``get_compose_activity`` reads the ``compose_activity_daily`` continuous aggregate on PostgreSQL and
``raw_events`` on SQLite; these check the two agree, including row order.
"""

import json
from collections.abc import Awaitable, Callable
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from sparkth.lib.analytics import Bucket, ingest_event
from sparkth.plugins.compose.analytics.reads import get_compose_activity

pytestmark = pytest.mark.pg


def _at(day: str, hour: int = 12) -> datetime:
    return datetime.fromisoformat(day).replace(hour=hour, tzinfo=timezone.utc)


async def _seed(session: AsyncSession, occurred_at: datetime, event_type: str, payload: dict[str, object]) -> None:
    await ingest_event(session, event_type, 1, payload, actor_id="1", occurred_at=occurred_at)


async def _seed_pre_outcome_tool(session: AsyncSession, occurred_at: datetime, tool_name: str) -> None:
    """A tool row as written before tool outcomes were recorded: no ``outcome`` key."""
    await session.execute(
        text(
            "INSERT INTO raw_events (occurred_at, received_at, event_type, event_version, actor_id, payload)"
            " VALUES (:at, :at, 'compose.tool_invoked', 1, '1', :payload)"
        ),
        {
            "at": occurred_at
            if session.bind.dialect.name == "postgresql"
            else occurred_at.strftime("%Y-%m-%d %H:%M:%S"),
            "payload": json.dumps({"conversation_id": "c", "tool_name": tool_name, "tool_category": "lms"}),
        },
    )
    await session.commit()


def _tool(name: str, outcome: str) -> dict[str, object]:
    return {
        "conversation_id": "c",
        "tool_name": name,
        "tool_category": "lms",
        "outcome": outcome,
        "failure_kind": None if outcome == "succeeded" else "unknown",
    }


def _search(result: str, chunks: int) -> dict[str, object]:
    return {
        "conversation_id": "c",
        "provider": "openai",
        "result": result,
        "chunks_found": chunks,
        "document_count": 1,
        "streamed": True,
    }


_MESSAGE: dict[str, object] = {
    "conversation_id": "c",
    "provider": "openai",
    "model": "m",
    "message_length": 5,
    "has_attachment": False,
}
_FAILED: dict[str, object] = {
    "conversation_id": None,
    "provider": None,
    "model": None,
    "cause": "llm_config_unusable",
    "streamed": False,
}


async def test_pg_compose_activity_cagg_exists(pg_analytics_session: AsyncSession) -> None:
    rows = await pg_analytics_session.execute(
        text(
            "SELECT view_name FROM timescaledb_information.continuous_aggregates"
            " WHERE view_name = 'compose_activity_daily'"
        )
    )
    assert rows.scalars().all() == ["compose_activity_daily"]


@pytest.mark.parametrize("bucket", list(Bucket))
async def test_pg_compose_activity_matches_sqlite(
    pg_analytics_session: AsyncSession,
    pg_refresh: Callable[[], Awaitable[None]],
    analytics_session: AsyncSession,
    bucket: Bucket,
) -> None:
    seed: list[tuple[datetime, str, dict[str, object]]] = [
        (_at("2025-11-30", 23), "compose.message_sent", _MESSAGE),
        (_at("2025-12-01", 0), "compose.message_sent", _MESSAGE),
        (_at("2025-12-01"), "compose.tool_invoked", _tool("createa", "succeeded")),
        (_at("2025-12-01"), "compose.tool_invoked", _tool("create_x", "failed")),
        (_at("2025-12-29"), "compose.tool_invoked", _tool("create_x", "succeeded")),
        (_at("2026-01-01"), "compose.turn_failed", _FAILED),
        (_at("2026-01-04", 23), "compose.message_sent", _MESSAGE),
        (
            _at("2026-01-31", 23),
            "compose.document_attached",
            {"conversation_id": "c", "document_id": 1, "source": "explicit"},
        ),
        (_at("2026-02-01", 0), "compose.message_sent", _MESSAGE),
        (_at("2025-12-01"), "compose.rag_search_completed", _search("found", 3)),
        (_at("2025-12-29"), "compose.rag_search_completed", _search("empty", 0)),
    ]
    for session in (pg_analytics_session, analytics_session):
        for occurred_at, event_type, payload in seed:
            await _seed(session, occurred_at, event_type, payload)
        await _seed_pre_outcome_tool(session, _at("2025-12-01"), "create_x")
    await pg_refresh()

    pg_result = await get_compose_activity(pg_analytics_session, date(2025, 12, 1), date(2026, 1, 31), bucket)
    sqlite_result = await get_compose_activity(analytics_session, date(2025, 12, 1), date(2026, 1, 31), bucket)

    assert pg_result == sqlite_result
    assert any(p.outcome is None and p.dimension == "create_x" for p in pg_result)
    assert any(p.event_type == "compose.rag_search_completed" and p.dimension == "empty" for p in pg_result)
