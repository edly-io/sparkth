"""Producer tests for ``compose.rag_search_completed`` on a streamed turn: a step's selection writes a real row.

Each drives ``ComposeStreamProcessor`` with a real attribution and the real analytics database; only the
provider, the chat service and the turn itself are stubbed.
"""

import uuid
from datetime import datetime, timezone
from functools import partial
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession as SQLAlchemyAsyncSession

from sparkth.core.analytics.models import raw_events
from sparkth.lib.rag import SectionSelection
from sparkth.plugins.compose.analytics.utils import AnalyticsAttribution
from sparkth.plugins.compose.detached import join_live_tasks
from sparkth.plugins.compose.routes.utils.stream_processor import ComposeStreamProcessor
from sparkth.plugins.compose.tests.conftest import STUB_AGENT
from sparkth.plugins.compose.tests.helpers import STREAM_TURN, handing_off_to, replay_turn, routed

EVENT = "compose.rag_search_completed"
CONVERSATION = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")

# The turns here are replayed, so the planner never runs.
PLANNER = handing_off_to(STUB_AGENT)

# A step that selected nothing, then the reply.
SELECTING_TURN = partial(
    replay_turn,
    [
        routed(STUB_AGENT.name),
        {"type": "structured_reply", "agent": STUB_AGENT.name, "reply": SectionSelection()},
        {"type": "token", "content": "Hello"},
    ],
)


def _provider() -> MagicMock:
    provider = MagicMock()
    provider.model = "gpt-4o"
    return provider


def _service() -> MagicMock:
    service = MagicMock()
    message = MagicMock()
    message.id = 1
    message.created_at = datetime.now(timezone.utc)
    service.add_message = AsyncMock(return_value=message)
    return service


def _conversation() -> MagicMock:
    conversation = MagicMock()
    conversation.id = 1
    conversation.uuid = CONVERSATION
    return conversation


async def _stream(service: MagicMock | None = None) -> None:
    with patch(STREAM_TURN, SELECTING_TURN):
        async for _ in ComposeStreamProcessor(
            _provider(),
            [{"role": "user", "content": "Create a course"}],
            _conversation(),
            service or _service(),
            None,
            1,
            analytics=AnalyticsAttribution(provider="openai", actor_id="1"),
            planner_setup=PLANNER,
        ).stream():
            pass
    await join_live_tasks()  # the stream task emits after its sentinel


async def _rows(analytics_session: SQLAlchemyAsyncSession, event_type: str = EVENT) -> list[dict[str, Any]]:
    rows = (await analytics_session.execute(sa_select(raw_events))).mappings().all()
    return [dict(r) for r in rows if r["event_type"] == event_type]


async def test_a_step_selection_records_a_search(analytics_session: SQLAlchemyAsyncSession) -> None:
    await _stream()

    [row] = await _rows(analytics_session)
    assert row["actor_id"] == "1"
    assert row["payload"] == {
        "conversation_id": str(CONVERSATION),
        "provider": "openai",
        "result": "empty",
        "chunks_found": 0,
        "document_count": 0,
        "streamed": True,
    }


async def test_a_failed_search_emit_leaves_no_error_message() -> None:
    """The emit runs after the guard: a failed write can't become an error in the transcript."""
    service = _service()
    with patch(
        "sparkth.plugins.compose.routes.utils.stream_processor.emit_rag_search_completed",
        new=AsyncMock(side_effect=RuntimeError("analytics down")),
    ):
        # The failure stays on the detached stream task; join_live_tasks gathers it, not raises.
        await _stream(service)
    assert not any(call.kwargs.get("is_error") for call in service.add_message.call_args_list)


async def test_a_failed_search_emit_still_records_the_completion(analytics_session: SQLAlchemyAsyncSession) -> None:
    with patch(
        "sparkth.plugins.compose.routes.utils.stream_processor.emit_rag_search_completed",
        new=AsyncMock(side_effect=RuntimeError("analytics down")),
    ):
        await _stream()

    assert len(await _rows(analytics_session, "compose.completion_served")) == 1
