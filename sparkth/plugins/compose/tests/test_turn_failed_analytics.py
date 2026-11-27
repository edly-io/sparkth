"""End-to-end analytics tests for failed turns.

Each drives a real request and asserts on rows that landed. `compose.turn_failed` is emitted
from a detached task — its seams raise rather than return — so these join it with `join_live_tasks`
before asserting.
"""

from collections.abc import AsyncGenerator, Sequence
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession as SQLAlchemyAsyncSession
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.analytics.models import raw_events
from sparkth.lib.models import User
from sparkth.plugins.compose.detached import join_live_tasks
from sparkth.plugins.compose.tests.helpers import (
    STREAM_TURN,
    answering_model,
    failing_model,
    seed_conversation,
    seed_llm_config,
)

COMPLETIONS_URL = "/api/v1/compose/completions"
_OPENAI_REQUEST = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")


async def _events(analytics_session: SQLAlchemyAsyncSession, event_type: str) -> list[dict[str, Any]]:
    rows = (await analytics_session.execute(sa_select(raw_events))).mappings().all()
    return [row["payload"] for row in rows if row["event_type"] == event_type]


def _provider() -> MagicMock:
    """A provider mock whose model answers; its ``send_message`` writes conversation titles."""
    provider = MagicMock()
    provider.model = "gpt-4o"
    provider.system_prompt = ""
    provider.create_llm.return_value = answering_model("Outline ready.")
    provider.send_message = AsyncMock(return_value={"content": "Outline ready.", "metadata": {}})
    return provider


def _dropped_connection_turn(
    messages: list[dict[str, Any]], tools: Sequence[Any], provider: Any, max_tool_executions: int
) -> AsyncGenerator[dict[str, Any], None]:
    """A streamed turn whose connection drops before the first event."""
    raise OSError("the connection dropped mid-stream")


async def _turn(
    client: AsyncClient,
    config_id: int,
    *,
    conversation_uuid: str | None = None,
    content: str = "Create a course on data privacy",
) -> Any:
    """One non-streaming turn, whose model calls are mocked."""
    body: dict[str, Any] = {
        "llm_config_id": config_id,
        "messages": [{"role": "user", "content": content}],
        "stream": False,
        "tools": "none",
    }
    if conversation_uuid:
        body["conversation_id"] = conversation_uuid
    return await client.post(COMPLETIONS_URL, json=body)


async def test_an_unusable_ai_key_records_a_failed_turn(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: SQLAlchemyAsyncSession,
) -> None:
    """The raise path: the route returns 404, so a queued emit would never run.

    ``provider`` and ``model`` are null because the config never resolved.
    """
    conversation_uuid = await seed_conversation(session, current_user.id or 1)

    response = await client.post(
        COMPLETIONS_URL,
        json={
            "llm_config_id": 99999,
            "conversation_id": conversation_uuid,
            "messages": [{"role": "user", "content": "Create a course"}],
            "stream": False,
            "tools": "none",
        },
    )
    await join_live_tasks()

    assert response.status_code == 404
    (failure,) = await _events(analytics_session, "compose.turn_failed")
    assert failure["cause"] == "llm_config_unusable"
    assert failure["provider"] is None
    assert failure["model"] is None
    assert failure["streamed"] is False
    # The turn failed before any message was stored, so there is none to count.
    assert await _events(analytics_session, "compose.message_sent") == []


async def test_a_provider_failure_records_a_failed_turn(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: SQLAlchemyAsyncSession,
) -> None:
    """The 500 path, which also raises."""
    config_id = await seed_llm_config(session, current_user.id or 1)
    conversation_uuid = await seed_conversation(session, current_user.id or 1)

    provider = _provider()
    provider.create_llm.return_value = failing_model(RuntimeError("upstream exploded"))

    with (
        patch("sparkth.plugins.compose.routes.completions.get_provider", return_value=provider),
        patch("sparkth.plugins.compose.classifiers.base.get_provider"),
    ):
        response = await _turn(client, config_id, conversation_uuid=conversation_uuid)
        await join_live_tasks()

    assert response.status_code == 500
    (failure,) = await _events(analytics_session, "compose.turn_failed")
    assert failure["cause"] == "unexpected"
    assert failure["provider"] == "openai"
    assert failure["model"] == "gpt-4o"
    assert failure["conversation_id"] == conversation_uuid
    # The instructor's message was stored before the route raised, so it still counts.
    (sent,) = await _events(analytics_session, "compose.message_sent")
    assert sent["conversation_id"] == conversation_uuid


async def test_a_successful_turn_records_no_failure(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: SQLAlchemyAsyncSession,
) -> None:
    config_id = await seed_llm_config(session, current_user.id or 1)
    conversation_uuid = await seed_conversation(session, current_user.id or 1)

    with (
        patch("sparkth.plugins.compose.routes.completions.get_provider", return_value=_provider()),
        patch("sparkth.plugins.compose.classifiers.base.get_provider"),
    ):
        await _turn(client, config_id, conversation_uuid=conversation_uuid)
        await join_live_tasks()

    assert await _events(analytics_session, "compose.turn_failed") == []


@pytest.mark.parametrize("streamed", [True, False])
async def test_the_failure_records_which_shape_the_client_asked_for(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: SQLAlchemyAsyncSession,
    streamed: bool,
) -> None:
    conversation_uuid = await seed_conversation(session, current_user.id or 1)

    response = await client.post(
        COMPLETIONS_URL,
        json={
            "llm_config_id": 99999,
            "conversation_id": conversation_uuid,
            "messages": [{"role": "user", "content": "Create a course"}],
            "stream": streamed,
            "tools": "none",
        },
    )
    await join_live_tasks()

    assert response.status_code == 404
    (failure,) = await _events(analytics_session, "compose.turn_failed")
    assert failure["streamed"] is streamed


async def test_a_streaming_failure_records_a_failed_turn(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: SQLAlchemyAsyncSession,
) -> None:
    """Streaming is the default client path, so a failure rate that omits it is misleading."""
    config_id = await seed_llm_config(session, current_user.id or 1)
    conversation_uuid = await seed_conversation(session, current_user.id or 1)

    with (
        patch("sparkth.plugins.compose.routes.completions.get_provider", return_value=_provider()),
        patch(STREAM_TURN, _dropped_connection_turn),
        patch("sparkth.plugins.compose.classifiers.base.get_provider"),
    ):
        response = await client.post(
            COMPLETIONS_URL,
            json={
                "llm_config_id": config_id,
                "conversation_id": conversation_uuid,
                "messages": [{"role": "user", "content": "Create a course on data privacy"}],
                "stream": True,
                "tools": "none",
            },
        )
        assert "data: " in response.text
        await join_live_tasks()

    (failure,) = await _events(analytics_session, "compose.turn_failed")
    assert failure["cause"] == "unexpected"
    assert failure["streamed"] is True
    assert failure["conversation_id"] == conversation_uuid
    (sent,) = await _events(analytics_session, "compose.message_sent")
    assert sent["conversation_id"] == conversation_uuid
