"""Tests for SSE status events during RAG retrieval."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core_plugins.chat.routes import stream_chat_response
from app.core_plugins.chat.schemas import ChatMessage
from app.rag.context_service import RAGContext, RAGContextService


def _make_rag_service(context: RAGContext) -> RAGContextService:
    mock_service = MagicMock(spec=RAGContextService)
    # Mock the two-phase RAG flow
    mock_service.rank_sections_for_query = AsyncMock(
        return_value=(context.source_name, [0.1] * 384, context.ranked_sections or [])
    )
    mock_service.search_with_embedding = AsyncMock(return_value=context.chunks)
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
    rag_context = RAGContext(
        file_db_id=42,
        source_name="doc.pdf",
        chunks=[],
        formatted_text="[DOCUMENT CONTEXT: doc.pdf]\nContent here.",
        ranked_sections=[
            {"chapter": None, "section": "**2. Data Privacy**", "subsection": None},
            {"chapter": None, "section": "**3. AI Ethics**", "subsection": None},
        ],
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
    ):
        events.append(chunk)

    # Parse SSE events
    parsed = []
    for event in events:
        if event.startswith("data:"):
            data = event.replace("data: ", "").strip()
            parsed.append(json.loads(data))

    statuses = [e for e in parsed if "status" in e]

    assert len(statuses) >= 2
    status_names = [e["status"] for e in statuses]
    assert "searching_document" in status_names
    # Check for section events (scanning and confirmed/removed)
    assert any(st.startswith("section_") for st in status_names)

    # Verify status events come before token events
    first_status_idx = next(i for i, e in enumerate(parsed) if "status" in e)
    first_token_idx = next((i for i, e in enumerate(parsed) if "token" in e and not e.get("done")), len(parsed))
    assert first_status_idx < first_token_idx


@pytest.mark.asyncio
async def test_sections_found_includes_section_names() -> None:
    rag_context = RAGContext(
        file_db_id=1,
        source_name="doc.pdf",
        chunks=[],
        formatted_text="context",
        ranked_sections=[
            {"chapter": None, "section": "**Data Privacy**", "subsection": None},
        ],
    )

    unresolved = [ChatMessage(role="user", content=[{"type": "drive_file", "file_id": 1}])]

    events = []
    async for chunk in stream_chat_response(
        provider=_make_provider(),
        messages=[{"role": "user", "content": [{"type": "drive_file", "file_id": 1}]}],
        conversation=_make_conversation(),
        service=_make_service(),
        session=AsyncMock(),
        tools=None,
        unresolved_messages=unresolved,
        rag_service=_make_rag_service(rag_context),
        user_id=1,
    ):
        events.append(chunk)

    parsed = []
    for event in events:
        if event.startswith("data:"):
            parsed.append(json.loads(event.replace("data: ", "").strip()))

    # Check that section scanning events include the section names
    section_events = [e for e in parsed if e.get("status") and e["status"].startswith("section_")]
    assert len(section_events) > 0, "Should have section status events"

    # Find any event that has the section info
    has_section = any("Data Privacy" in str(e.get("section", {}).get("name", "")) for e in section_events)
    assert has_section, f"Should find 'Data Privacy' in section events: {section_events}"


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

    rag_context = RAGContext(
        file_db_id=1,
        source_name="guide.pdf",
        chunks=[MagicMock()],  # non-empty so sections aren't dropped
        formatted_text="[DOCUMENT CONTEXT: guide.pdf]\nContent.",
        ranked_sections=[
            {"chapter": None, "section": "**Introduction**", "subsection": None},
            {"chapter": None, "section": "**Conclusion**", "subsection": None},
        ],
    )

    unresolved = [ChatMessage(role="user", content=[{"type": "drive_file", "file_id": 1}])]
    service = _make_service()

    # Make search_with_embedding return results whose .chunk.section matches ranked sections
    sr1 = MagicMock()
    sr1.chunk.section = "**Introduction**"
    sr1.chunk.chapter = None
    sr1.chunk.subsection = None
    sr1.chunk.content = "Intro content"
    sr2 = MagicMock()
    sr2.chunk.section = "**Conclusion**"
    sr2.chunk.chapter = None
    sr2.chunk.subsection = None
    sr2.chunk.content = "Conclusion content"
    mock_rag = MagicMock(spec=RAGContextService)
    mock_rag.rank_sections_for_query = AsyncMock(
        return_value=("guide.pdf", [0.1] * 384, rag_context.ranked_sections or [])
    )
    mock_rag.search_with_embedding = AsyncMock(return_value=[sr1, sr2])

    async for _ in stream_chat_response(
        provider=_make_provider(),
        messages=[{"role": "user", "content": [{"type": "drive_file", "file_id": 1}]}],
        conversation=_make_conversation(),
        service=service,
        session=AsyncMock(),
        tools=None,
        unresolved_messages=unresolved,
        rag_service=mock_rag,
        user_id=1,
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
