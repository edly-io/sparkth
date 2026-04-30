"""Tests for SSE status events during RAG retrieval."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core_plugins.chat.routes import stream_chat_response
from app.core_plugins.chat.schemas import ChatMessage
from app.rag.context_service import RAGContext, RAGContextService


def _make_rag_service(context: RAGContext) -> RAGContextService:
    mock_service = MagicMock(spec=RAGContextService)
    mock_service.get_context_via_agent = AsyncMock(return_value=context)
    mock_service.get_context_for_drive_file = AsyncMock(return_value=context)
    return mock_service


def _make_provider() -> MagicMock:
    provider = MagicMock()

    async def stream_gen(*args: object, **kwargs: object) -> object:
        yield "Hello"
        yield " world"

    provider.stream_message = stream_gen
    return provider


def _make_service() -> MagicMock:
    service = MagicMock()
    msg = MagicMock()
    msg.id = 1
    service.add_message = AsyncMock(return_value=msg)
    return service


def _make_conversation() -> MagicMock:
    conv = MagicMock()
    conv.id = 1
    import uuid

    conv.uuid = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
    return conv


@pytest.mark.asyncio
async def test_status_events_emitted_before_tokens() -> None:
    sr = MagicMock()
    sr.chunk.chapter = None
    sr.chunk.section = "Content"
    sr.chunk.subsection = None

    rag_context = RAGContext(
        file_db_id=42,
        source_name="doc.pdf",
        chunks=[sr],
        formatted_text="[DOCUMENT CONTEXT: doc.pdf]\nContent here.",
    )

    unresolved = [
        ChatMessage(
            role="user", content=[{"type": "drive_file", "file_id": 42}, {"type": "text", "text": "Create a course"}]
        )
    ]

    events = []
    async for chunk in stream_chat_response(
        provider=_make_provider(),
        messages=[{"role": "user", "content": [{"type": "drive_file", "file_id": 42}]}],
        conversation=_make_conversation(),
        service=_make_service(),
        session=AsyncMock(),
        tools=None,
        unresolved_messages=unresolved,
        rag_service=_make_rag_service(rag_context),
        user_id=1,
        llm=MagicMock(),
    ):
        events.append(chunk)

    # Parse SSE events
    parsed = []
    for event in events:
        if event.startswith("data:"):
            parsed.append(json.loads(event.replace("data: ", "").strip()))

    statuses = [e for e in parsed if "status" in e]
    status_names = [e["status"] for e in statuses]

    assert "searching_document" in status_names
    assert "generating" in status_names

    # Status events must precede token events
    first_status_idx = next(i for i, e in enumerate(parsed) if "status" in e)
    first_token_idx = next((i for i, e in enumerate(parsed) if "token" in e and not e.get("done")), len(parsed))
    assert first_status_idx < first_token_idx


@pytest.mark.asyncio
async def test_agent_context_injected_into_messages() -> None:
    """Agent-retrieved context is injected into messages before the LLM call."""
    chunk = MagicMock()
    chunk.chapter = None
    chunk.section = "Data Privacy"
    chunk.subsection = None
    chunk.content = "Data privacy content."
    chunk.id = 10

    sr = MagicMock()
    sr.chunk = chunk
    sr.similarity = 1.0

    rag_context = RAGContext(
        file_db_id=1,
        source_name="doc.pdf",
        chunks=[sr],
        formatted_text="[DOCUMENT CONTEXT: doc.pdf]\nData privacy content.",
    )

    original_messages = [{"role": "user", "content": [{"type": "drive_file", "file_id": 1}]}]
    unresolved = [ChatMessage(role="user", content=[{"type": "drive_file", "file_id": 1}])]

    async for _ in stream_chat_response(
        provider=_make_provider(),
        messages=original_messages,
        conversation=_make_conversation(),
        service=_make_service(),
        session=AsyncMock(),
        tools=None,
        unresolved_messages=unresolved,
        rag_service=_make_rag_service(rag_context),
        user_id=1,
        llm=MagicMock(),
    ):
        pass

    # The drive_file block should have been replaced with the RAG text
    content = original_messages[0]["content"]
    assert isinstance(content, list)
    injected = [b for b in content if isinstance(b, dict) and b.get("type") == "text"]
    assert len(injected) == 1
    assert "Data privacy content." in injected[0]["text"]


@pytest.mark.asyncio
async def test_no_status_events_without_drive_file_blocks() -> None:
    """When no unresolved_messages passed, no status events are emitted."""
    events = []
    async for chunk in stream_chat_response(
        provider=_make_provider(),
        messages=[{"role": "user", "content": "Hello"}],
        conversation=_make_conversation(),
        service=_make_service(),
        session=AsyncMock(),
        tools=None,
    ):
        events.append(chunk)

    parsed = []
    for event in events:
        if event.startswith("data:"):
            parsed.append(json.loads(event.replace("data: ", "").strip()))

    statuses = [e for e in parsed if "status" in e]
    assert len(statuses) == 0


@pytest.mark.asyncio
async def test_confirmed_rag_sections_saved_as_metadata() -> None:
    """Confirmed RAG sections are persisted in model_metadata when saving the assistant message."""

    sr1 = MagicMock()
    sr1.chunk.section = "Introduction"
    sr1.chunk.chapter = None
    sr1.chunk.subsection = None
    sr1.chunk.content = "Intro content"
    sr2 = MagicMock()
    sr2.chunk.section = "Conclusion"
    sr2.chunk.chapter = None
    sr2.chunk.subsection = None
    sr2.chunk.content = "Conclusion content"

    rag_context = RAGContext(
        file_db_id=1,
        source_name="guide.pdf",
        chunks=[sr1, sr2],
        formatted_text="[DOCUMENT CONTEXT: guide.pdf]\nContent.",
    )

    unresolved = [ChatMessage(role="user", content=[{"type": "drive_file", "file_id": 1}])]
    service = _make_service()

    async for _ in stream_chat_response(
        provider=_make_provider(),
        messages=[{"role": "user", "content": [{"type": "drive_file", "file_id": 1}]}],
        conversation=_make_conversation(),
        service=service,
        session=AsyncMock(),
        tools=None,
        unresolved_messages=unresolved,
        rag_service=_make_rag_service(rag_context),
        user_id=1,
        llm=MagicMock(),
    ):
        pass

    # The last add_message call (assistant message) should include rag_sections in metadata
    add_message_calls = service.add_message.call_args_list
    assistant_call = next(
        (c for c in add_message_calls if c.kwargs.get("role") == "assistant"),
        None,
    )
    assert assistant_call is not None, "add_message should have been called for the assistant"
    metadata = assistant_call.kwargs.get("metadata")
    assert metadata is not None, "metadata should be passed when RAG sections were confirmed"
    sections = metadata.get("rag_sections")
    assert sections is not None, "rag_sections key should be present in metadata"
    assert len(sections) == 2
    names = {s["name"] for s in sections}
    assert "Introduction" in names
    assert "Conclusion" in names


@pytest.mark.asyncio
async def test_no_rag_sections_metadata_without_drive_files() -> None:
    """When no drive files are processed, add_message is called without rag_sections metadata."""
    service = _make_service()

    async for _ in stream_chat_response(
        provider=_make_provider(),
        messages=[{"role": "user", "content": "Hello"}],
        conversation=_make_conversation(),
        service=service,
        session=AsyncMock(),
        tools=None,
    ):
        pass

    add_message_calls = service.add_message.call_args_list
    assistant_call = next(
        (c for c in add_message_calls if c.kwargs.get("role") == "assistant"),
        None,
    )
    assert assistant_call is not None
    metadata = assistant_call.kwargs.get("metadata")
    # No drive files → metadata should be absent or have no rag_sections
    assert metadata is None or metadata.get("rag_sections") is None


class TestMessageResponseRagSections:
    def test_message_response_accepts_rag_sections(self) -> None:
        from datetime import datetime

        from app.core_plugins.chat.schemas import MessageResponse

        response = MessageResponse(
            id=1,
            role="assistant",
            content="Here is your answer.",
            tokens_used=None,
            cost=None,
            created_at=datetime(2024, 1, 1),
            message_type="text",
            attachment_name=None,
            attachment_size=None,
            rag_sections=[{"type": "section", "name": "Introduction", "source": "doc.pdf"}],
        )
        assert response.rag_sections is not None
        assert len(response.rag_sections) == 1
        assert response.rag_sections[0]["name"] == "Introduction"

    def test_message_response_rag_sections_defaults_to_none(self) -> None:
        from datetime import datetime

        from app.core_plugins.chat.schemas import MessageResponse

        response = MessageResponse(
            id=1,
            role="assistant",
            content="Hello.",
            tokens_used=None,
            cost=None,
            created_at=datetime(2024, 1, 1),
            message_type="text",
            attachment_name=None,
            attachment_size=None,
        )
        assert response.rag_sections is None
