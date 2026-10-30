"""Producer tests for ``chat.rag_search_completed``: both retrieval seams write a real row.

The streamed path drives ``ComposeStreamProcessor`` with a real attribution and the real analytics
database; only the provider, the chat service and retrieval itself are stubbed. The non-streamed
path runs ``resolve_document_blocks`` with a real ``ComposeTurnAnalytics`` and runs its queued tasks.
"""

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import BackgroundTasks
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession as SQLAlchemyAsyncSession

from sparkth.core.analytics.models import raw_events
from sparkth.lib.documents import Document, DocumentStatus
from sparkth.lib.rag import RAGRetrievalError, RetrievedChunk
from sparkth.plugins.compose.analytics.utils import AnalyticsAttribution, ComposeTurnAnalytics
from sparkth.plugins.compose.detached import join_live_tasks
from sparkth.plugins.compose.models import Message
from sparkth.plugins.compose.routes.utils.message_assembly import assemble_provider_messages
from sparkth.plugins.compose.routes.utils.rag_search import resolve_document_blocks
from sparkth.plugins.compose.routes.utils.stream_processor import ComposeStreamProcessor
from sparkth.plugins.compose.schemas import ChatCompletionRequest, ChatMessage

EVENT = "chat.rag_search_completed"
CONVERSATION = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")


def _chunk(section: str = "Intro") -> RetrievedChunk:
    return RetrievedChunk(source_name="doc.pdf", chapter=None, section=section, subsection=None, content="text")


def _turn() -> list[ChatMessage]:
    return [
        ChatMessage(
            role="user",
            content=[
                {"type": "drive_file", "file_id": 42},
                {"type": "drive_file", "file_id": 43},
                {"type": "text", "text": "Create a course"},
            ],
        )
    ]


def _provider() -> MagicMock:
    provider = MagicMock()
    provider.model = "gpt-4o"

    async def stream(*args: object, **kwargs: object) -> Any:
        yield {"type": "token", "content": "Hello"}

    provider.stream_message = stream
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


async def _stream(retrieve: AsyncMock, service: MagicMock | None = None) -> None:
    with patch("sparkth.plugins.compose.routes.utils.stream_processor.agentic_retrieve_context", new=retrieve):
        async for _ in ComposeStreamProcessor(
            _provider(),
            [{"role": "user", "content": "Create a course"}],
            _conversation(),
            service or _service(),
            None,
            _turn(),
            1,
            MagicMock(),
            True,
            analytics=AnalyticsAttribution(provider="openai", actor_id="1"),
        ).stream():
            pass
    await join_live_tasks()  # the stream task emits after its sentinel


async def _rows(analytics_session: SQLAlchemyAsyncSession, event_type: str = EVENT) -> list[dict[str, Any]]:
    rows = (await analytics_session.execute(sa_select(raw_events))).mappings().all()
    return [dict(r) for r in rows if r["event_type"] == event_type]


async def test_streamed_search_records_found(analytics_session: SQLAlchemyAsyncSession) -> None:
    await _stream(AsyncMock(return_value=[_chunk("Intro"), _chunk("Outro"), _chunk("Intro")]))

    [row] = await _rows(analytics_session)
    assert row["actor_id"] == "1"
    assert row["payload"] == {
        "conversation_id": str(CONVERSATION),
        "provider": "openai",
        "result": "found",
        "chunks_found": 3,
        "document_count": 2,
        "streamed": True,
    }


async def test_streamed_empty_search_records_empty(analytics_session: SQLAlchemyAsyncSession) -> None:
    """The no-results reply ends the turn with no completion; the search still lands."""
    await _stream(AsyncMock(return_value=[]))

    [row] = await _rows(analytics_session)
    assert row["payload"]["result"] == "empty"
    assert row["payload"]["chunks_found"] == 0
    assert await _rows(analytics_session, "chat.completion_served") == []


async def test_streamed_retrieval_error_records_no_search(analytics_session: SQLAlchemyAsyncSession) -> None:
    await _stream(AsyncMock(side_effect=RAGRetrievalError("boom")))

    assert await _rows(analytics_session) == []
    [failed] = await _rows(analytics_session, "chat.turn_failed")
    assert failed["payload"]["cause"] == "rag_retrieval_error"


async def test_streamed_turn_without_search_records_nothing(analytics_session: SQLAlchemyAsyncSession) -> None:
    retrieve = AsyncMock(return_value=[_chunk()])
    with patch("sparkth.plugins.compose.routes.utils.stream_processor.agentic_retrieve_context", new=retrieve):
        async for _ in ComposeStreamProcessor(
            _provider(),
            [{"role": "user", "content": "Hello"}],
            _conversation(),
            _service(),
            None,
            analytics=AnalyticsAttribution(provider="openai", actor_id="1"),
        ).stream():
            pass
    await join_live_tasks()

    retrieve.assert_not_awaited()
    assert await _rows(analytics_session) == []


async def test_streamed_emit_failure_leaves_no_error_message() -> None:
    """The emit runs after the guard: a failed write can't become an error in the transcript."""
    service = _service()
    with patch(
        "sparkth.plugins.compose.routes.utils.stream_processor.emit_rag_search_completed",
        new=AsyncMock(side_effect=RuntimeError("analytics down")),
    ):
        # The failure stays on the detached stream task; join_live_tasks gathers it, not raises.
        await _stream(AsyncMock(return_value=[]), service)
    assert not any(call.kwargs.get("is_error") for call in service.add_message.call_args_list)


async def test_streamed_search_emit_failure_still_records_the_completion(
    analytics_session: SQLAlchemyAsyncSession,
) -> None:
    with patch(
        "sparkth.plugins.compose.routes.utils.stream_processor.emit_rag_search_completed",
        new=AsyncMock(side_effect=RuntimeError("analytics down")),
    ):
        await _stream(AsyncMock(return_value=[_chunk()]))

    assert len(await _rows(analytics_session, "chat.completion_served")) == 1


async def test_non_streamed_search_records_event(analytics_session: SQLAlchemyAsyncSession) -> None:
    tasks = BackgroundTasks()
    analytics = ComposeTurnAnalytics(
        background_tasks=tasks, conversation_id="c-1", provider="openai", model="gpt-4o", actor_id="1"
    )
    with patch(
        "sparkth.plugins.compose.routes.utils.rag_search.agentic_retrieve_context",
        new=AsyncMock(return_value=[]),
    ):
        await resolve_document_blocks(messages=_turn(), llm=MagicMock(), analytics=analytics)
    await tasks()

    [row] = await _rows(analytics_session)
    assert row["payload"] == {
        "conversation_id": "c-1",
        "provider": "openai",
        "result": "empty",
        "chunks_found": 0,
        "document_count": 2,
        "streamed": False,
    }


async def test_assemble_passes_analytics_to_non_streamed_search(analytics_session: SQLAlchemyAsyncSession) -> None:
    tasks = BackgroundTasks()
    analytics = ComposeTurnAnalytics(
        background_tasks=tasks, conversation_id="c-1", provider="openai", model="gpt-4o", actor_id="1"
    )
    request = ChatCompletionRequest(
        llm_config_id=1, messages=[ChatMessage(role="user", content="Create a course")], stream=False
    )
    document = Document(id=42, user_id=1, name="doc.pdf", status=DocumentStatus.READY)
    with patch(
        "sparkth.plugins.compose.routes.utils.rag_search.agentic_retrieve_context",
        new=AsyncMock(return_value=[_chunk()]),
    ):
        await assemble_provider_messages(
            request,
            [Message(conversation_id=1, role="user", content="Create a course")],
            [document],
            "Create a course",
            True,
            MagicMock(),
            analytics=analytics,
        )
    await tasks()

    [row] = await _rows(analytics_session)
    assert row["payload"]["result"] == "found"
    assert row["payload"]["streamed"] is False
