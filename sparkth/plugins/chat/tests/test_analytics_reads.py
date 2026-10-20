"""Tests for the chat activity read: ``get_chat_activity`` and ``GET /api/v1/chat/analytics/activity``."""

import json
from datetime import date, datetime, timezone
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession as SQLAlchemyAsyncSession
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.analytics import Bucket, ingest_event, summarize
from sparkth.lib.models import User
from sparkth.lib.testing import grant_global_permission
from sparkth.plugins.chat.analytics.reads import ChatActivityPoint, get_chat_activity

URL = "/api/v1/chat/analytics/activity"

_PAYLOADS: dict[str, dict[str, Any]] = {
    "chat.conversation_started": {"conversation_id": "c", "provider": "openai", "model": "m"},
    "chat.message_sent": {
        "conversation_id": "c",
        "provider": "openai",
        "model": "m",
        "message_length": 5,
        "has_attachment": False,
    },
    "chat.document_attached": {"conversation_id": "c", "document_id": 1, "source": "explicit"},
    "chat.document_detached": {"conversation_id": "c", "document_id": 1, "seconds_attached": 3},
}


def _at(day: str, hour: int = 12) -> datetime:
    return datetime.fromisoformat(day).replace(hour=hour, tzinfo=timezone.utc)


async def _seed(session: SQLAlchemyAsyncSession, event_type: str, occurred_at: datetime) -> None:
    await ingest_event(session, event_type, 1, _PAYLOADS[event_type], actor_id="1", occurred_at=occurred_at)


async def _seed_tool(
    session: SQLAlchemyAsyncSession, occurred_at: datetime, tool_name: str, outcome: str = "succeeded"
) -> None:
    await ingest_event(
        session,
        "chat.tool_invoked",
        1,
        {
            "conversation_id": "c",
            "tool_name": tool_name,
            "tool_category": "lms",
            "outcome": outcome,
            "failure_kind": None if outcome == "succeeded" else "unknown",
        },
        actor_id="1",
        occurred_at=occurred_at,
    )


async def _seed_failed_turn(session: SQLAlchemyAsyncSession, occurred_at: datetime, cause: str) -> None:
    await ingest_event(
        session,
        "chat.turn_failed",
        1,
        {"conversation_id": "c", "provider": "openai", "model": "m", "cause": cause, "streamed": True},
        actor_id="1",
        occurred_at=occurred_at,
    )


async def _seed_pre_outcome_tool(session: SQLAlchemyAsyncSession, occurred_at: datetime, tool_name: str) -> None:
    """A tool row as written before tool outcomes were recorded: no ``outcome`` key."""
    stamp = occurred_at.strftime("%Y-%m-%d %H:%M:%S")
    await session.execute(
        text(
            "INSERT INTO raw_events (occurred_at, received_at, event_type, event_version, actor_id, payload)"
            " VALUES (:at, :at, 'chat.tool_invoked', 1, '1', :payload)"
        ),
        {"at": stamp, "payload": json.dumps({"conversation_id": "c", "tool_name": tool_name, "tool_category": "lms"})},
    )
    await session.commit()


async def test_counts_each_event_type_per_day(analytics_session: SQLAlchemyAsyncSession) -> None:
    for event_type in _PAYLOADS:
        await _seed(analytics_session, event_type, _at("2026-03-02"))
    await _seed(analytics_session, "chat.message_sent", _at("2026-03-02", 23))
    await _seed(analytics_session, "chat.message_sent", _at("2026-03-03", 0))

    result = await get_chat_activity(analytics_session, date(2026, 3, 1), date(2026, 3, 31), Bucket.day)

    assert result == [
        ChatActivityPoint(bucket="2026-03-02", event_type="chat.conversation_started", event_count=1),
        ChatActivityPoint(bucket="2026-03-02", event_type="chat.document_attached", event_count=1),
        ChatActivityPoint(bucket="2026-03-02", event_type="chat.document_detached", event_count=1),
        ChatActivityPoint(bucket="2026-03-02", event_type="chat.message_sent", event_count=2),
        ChatActivityPoint(bucket="2026-03-03", event_type="chat.message_sent", event_count=1),
    ]


async def test_dimension_is_tool_name_or_cause_and_outcome_splits_tools(
    analytics_session: SQLAlchemyAsyncSession,
) -> None:
    await _seed_tool(analytics_session, _at("2026-03-02"), "create_course")
    await _seed_tool(analytics_session, _at("2026-03-02"), "create_course", outcome="failed")
    await _seed_tool(analytics_session, _at("2026-03-02"), "create_course")
    await _seed_pre_outcome_tool(analytics_session, _at("2026-03-02"), "create_course")
    await _seed_failed_turn(analytics_session, _at("2026-03-02"), "provider_api_error")

    result = await get_chat_activity(analytics_session, date(2026, 3, 2), date(2026, 3, 2), Bucket.day)

    assert result == [
        ChatActivityPoint(
            bucket="2026-03-02", event_type="chat.tool_invoked", dimension="create_course", event_count=1
        ),
        ChatActivityPoint(
            bucket="2026-03-02",
            event_type="chat.tool_invoked",
            dimension="create_course",
            outcome="failed",
            event_count=1,
        ),
        ChatActivityPoint(
            bucket="2026-03-02",
            event_type="chat.tool_invoked",
            dimension="create_course",
            outcome="succeeded",
            event_count=2,
        ),
        ChatActivityPoint(
            bucket="2026-03-02", event_type="chat.turn_failed", dimension="provider_api_error", event_count=1
        ),
    ]


async def test_activity_counts_searches_by_result(analytics_session: SQLAlchemyAsyncSession) -> None:
    for result, chunks in (("found", 3), ("empty", 0), ("empty", 0)):
        await ingest_event(
            analytics_session,
            "chat.rag_search_completed",
            1,
            {
                "conversation_id": "c",
                "provider": "openai",
                "result": result,
                "chunks_found": chunks,
                "document_count": 1,
                "streamed": True,
            },
            actor_id="1",
            occurred_at=_at("2026-03-02"),
        )

    points = await get_chat_activity(analytics_session, date(2026, 3, 1), date(2026, 3, 31), Bucket.month)

    assert [(p.event_type, p.dimension, p.event_count) for p in points] == [
        ("chat.rag_search_completed", "empty", 2),
        ("chat.rag_search_completed", "found", 1),
    ]


async def test_week_buckets_start_monday_and_month_buckets_the_first(analytics_session: SQLAlchemyAsyncSession) -> None:
    # 2025-12-29 is a Monday; that week runs to Sunday 2026-01-04.
    for day in ("2025-12-29", "2026-01-04", "2026-01-05"):
        await _seed(analytics_session, "chat.message_sent", _at(day))

    weeks = await get_chat_activity(analytics_session, date(2025, 12, 1), date(2026, 1, 31), Bucket.week)
    months = await get_chat_activity(analytics_session, date(2025, 12, 1), date(2026, 1, 31), Bucket.month)

    assert [(p.bucket, p.event_count) for p in weeks] == [("2025-12-29", 2), ("2026-01-05", 1)]
    assert [(p.bucket, p.event_count) for p in months] == [("2025-12-01", 1), ("2026-01-01", 2)]


async def test_range_is_inclusive_on_both_ends(analytics_session: SQLAlchemyAsyncSession) -> None:
    for at in (_at("2026-02-28", 23), _at("2026-03-01", 0), _at("2026-03-10", 23), _at("2026-03-11", 0)):
        await _seed(analytics_session, "chat.message_sent", at)

    result = await get_chat_activity(analytics_session, date(2026, 3, 1), date(2026, 3, 10), Bucket.day)

    assert [p.bucket for p in result] == ["2026-03-01", "2026-03-10"]


async def test_ignores_events_outside_the_activity_set(analytics_session: SQLAlchemyAsyncSession) -> None:
    await ingest_event(
        analytics_session,
        "chat.scope_classified",
        1,
        {
            "conversation_id": "c",
            "provider": "openai",
            "classifier_model": "m",
            "verdict": "in_scope",
            "history_turns": 0,
            "attachment_count": 0,
            "query_length": 3,
        },
        actor_id="1",
        occurred_at=_at("2026-03-02"),
    )

    assert await get_chat_activity(analytics_session, date(2026, 3, 1), date(2026, 3, 31), Bucket.day) == []


async def test_orders_null_dimension_and_outcome_first(analytics_session: SQLAlchemyAsyncSession) -> None:
    await _seed_tool(analytics_session, _at("2026-03-02"), "createa")
    await _seed_tool(analytics_session, _at("2026-03-02"), "create_x")
    await _seed_pre_outcome_tool(analytics_session, _at("2026-03-02"), "create_x")

    result = await get_chat_activity(analytics_session, date(2026, 3, 2), date(2026, 3, 2), Bucket.day)

    assert [(p.dimension, p.outcome) for p in result] == [
        ("create_x", None),
        ("create_x", "succeeded"),
        ("createa", "succeeded"),
    ]


async def _as_reader(session: AsyncSession, user: User) -> None:
    session.add(user)
    await session.flush()
    await grant_global_permission(session, 1, "analytics.read")
    await session.commit()


async def test_endpoint_returns_points_for_permitted_user(
    client: AsyncClient, current_user: User, session: AsyncSession, analytics_session: SQLAlchemyAsyncSession
) -> None:
    await _as_reader(session, current_user)
    await _seed_tool(analytics_session, _at("2026-03-02"), "create_course")

    response = await client.get(URL, params={"from": "2026-03-01", "to": "2026-03-31", "bucket": "week"})

    assert response.status_code == 200
    assert response.json() == [
        {
            "bucket": "2026-03-02",
            "event_type": "chat.tool_invoked",
            "dimension": "create_course",
            "outcome": "succeeded",
            "event_count": 1,
        }
    ]


@pytest.mark.parametrize(
    "params",
    [
        {"from": "2026-03-10", "to": "2026-03-09"},
        {"from": "2025-01-01", "to": "2026-01-02"},
        {"from": "2026-03-01", "to": "2026-03-31", "bucket": "year"},
    ],
    ids=["from-after-to", "span-367-days", "unknown-bucket"],
)
async def test_endpoint_rejects_invalid_query(
    client: AsyncClient, current_user: User, session: AsyncSession, params: dict[str, str]
) -> None:
    await _as_reader(session, current_user)

    response = await client.get(URL, params=params)

    assert response.status_code == 422


async def test_endpoint_forbidden_without_permission(client: AsyncClient, current_user: User) -> None:
    response = await client.get(URL, params={"from": "2026-03-01", "to": "2026-03-31"})

    assert response.status_code == 403


async def test_endpoint_requires_authentication(client: AsyncClient) -> None:
    response = await client.get(URL, params={"from": "2026-03-01", "to": "2026-03-31"})

    assert response.status_code == 401


async def test_chat_figures_count_their_event_type_for_both_periods(analytics_session: SQLAlchemyAsyncSession) -> None:
    await _seed(analytics_session, "chat.conversation_started", _at("2026-03-12"))
    await _seed(analytics_session, "chat.message_sent", _at("2026-03-12"))
    await _seed(analytics_session, "chat.message_sent", _at("2026-03-13"))
    await _seed(analytics_session, "chat.message_sent", _at("2026-03-05"))  # previous period

    rows = await summarize(analytics_session, date(2026, 3, 11), date(2026, 3, 20))

    chat = {r.key: (r.label, r.view, r.plugin, r.current, r.previous) for r in rows if r.plugin == "chat"}
    assert chat == {
        "chat.conversations": ("Conversations started", "authoring", "chat", 1, 0),
        "chat.messages": ("Messages sent", "authoring", "chat", 2, 1),
        "chat.tool_calls": ("Tool calls", "authoring", "chat", 0, 0),
        "chat.failed_turns": ("Messages failed", "authoring", "chat", 0, 0),
    }
    assert [r.key for r in rows if r.plugin == "chat"] == list(chat)  # in their own order
