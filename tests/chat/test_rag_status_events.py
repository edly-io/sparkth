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
        yield {"type": "token", "content": "Hello"}
        yield {"type": "token", "content": " world"}

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

    # The drive_file block should be gone; two text blocks remain:
    # [0] context-retention prompt, [1] the RAG context
    content = original_messages[0]["content"]
    assert isinstance(content, list)
    injected = [b for b in content if isinstance(b, dict) and b.get("type") == "text"]
    assert len(injected) == 2
    assert "context" in injected[0]["text"].lower()
    assert "Data privacy content." in injected[1]["text"]


@pytest.mark.asyncio
async def test_multi_file_rag_context_preserved() -> None:
    """RAG context from file₁ is not dropped when file₂ is processed in the same message."""

    def _make_context(file_db_id: int, source: str, text: str) -> RAGContext:
        sr = MagicMock()
        sr.chunk.chapter = None
        sr.chunk.section = "Section"
        sr.chunk.subsection = None
        sr.chunk.id = file_db_id
        return RAGContext(file_db_id=file_db_id, source_name=source, chunks=[sr], formatted_text=text)

    ctx1 = _make_context(1, "file1.pdf", "Context from file 1.")
    ctx2 = _make_context(2, "file2.pdf", "Context from file 2.")

    async def _get_context(session: object, user_id: object, file_db_id: int, **_: object) -> RAGContext:
        return ctx1 if file_db_id == 1 else ctx2

    rag_service = MagicMock(spec=RAGContextService)
    rag_service.get_context_via_agent = _get_context

    original_messages = [
        {"role": "user", "content": [{"type": "drive_file", "file_id": 1}, {"type": "drive_file", "file_id": 2}]}
    ]
    unresolved = [
        ChatMessage(
            role="user",
            content=[{"type": "drive_file", "file_id": 1}, {"type": "drive_file", "file_id": 2}],
        )
    ]

    async for _ in stream_chat_response(
        provider=_make_provider(),
        messages=original_messages,
        conversation=_make_conversation(),
        service=_make_service(),
        session=AsyncMock(),
        tools=None,
        unresolved_messages=unresolved,
        rag_service=rag_service,
        user_id=1,
        llm=MagicMock(),
    ):
        pass

    content = original_messages[0]["content"]
    assert isinstance(content, list)
    text_blocks = [b["text"] for b in content if isinstance(b, dict) and b.get("type") == "text"]
    # context prompt + two RAG context blocks — neither file's context is lost
    assert len(text_blocks) == 3
    assert any("Context from file 1." in t for t in text_blocks)
    assert any("Context from file 2." in t for t in text_blocks)


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


class TestParseToolCalls:
    def test_returns_none_for_no_metadata(self) -> None:
        from app.core_plugins.chat.routes import _parse_tool_calls

        assert _parse_tool_calls(None) is None

    def test_returns_none_for_empty_metadata(self) -> None:
        from app.core_plugins.chat.routes import _parse_tool_calls

        assert _parse_tool_calls("{}") is None

    def test_returns_none_for_invalid_json(self) -> None:
        from app.core_plugins.chat.routes import _parse_tool_calls

        assert _parse_tool_calls("not-json") is None

    def test_returns_none_when_tool_calls_not_list(self) -> None:
        import json

        from app.core_plugins.chat.routes import _parse_tool_calls

        assert _parse_tool_calls(json.dumps({"tool_calls": "bad"})) is None

    def test_returns_tool_calls_list(self) -> None:
        import json

        from app.core_plugins.chat.routes import _parse_tool_calls

        meta = json.dumps({"tool_calls": [{"name": "search_web"}, {"name": "search_web"}]})
        result = _parse_tool_calls(meta)
        assert result is not None
        assert len(result) == 2
        assert result[0]["name"] == "search_web"

    def test_ignores_rag_sections_key(self) -> None:
        import json

        from app.core_plugins.chat.routes import _parse_tool_calls

        meta = json.dumps({"rag_sections": [{"type": "section", "name": "Intro"}]})
        assert _parse_tool_calls(meta) is None


@pytest.mark.asyncio
async def test_tool_calls_saved_in_metadata() -> None:
    """Tool call names are persisted in message metadata when tools are invoked."""
    service = _make_service()

    provider = MagicMock()

    async def stream_gen(*args: object, **kwargs: object) -> object:
        yield {"type": "tool_start", "name": "search_web"}
        yield {"type": "tool_end", "name": "search_web"}
        yield {"type": "token", "content": "Result"}

    provider.stream_message = stream_gen

    async for _ in stream_chat_response(
        provider=provider,
        messages=[{"role": "user", "content": "search for something"}],
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
    assert metadata is not None
    assert "tool_calls" in metadata
    assert metadata["tool_calls"] == [{"name": "search_web"}]


@pytest.mark.asyncio
async def test_tool_calls_in_done_payload() -> None:
    """The done SSE payload includes tool_calls so the frontend can confirm them."""
    provider = MagicMock()

    async def stream_gen(*args: object, **kwargs: object) -> object:
        yield {"type": "tool_start", "name": "get_data"}
        yield {"type": "tool_end", "name": "get_data"}
        yield {"type": "token", "content": "Done"}

    provider.stream_message = stream_gen

    events = []
    async for chunk in stream_chat_response(
        provider=provider,
        messages=[{"role": "user", "content": "run a tool"}],
        conversation=_make_conversation(),
        service=_make_service(),
        session=AsyncMock(),
        tools=None,
    ):
        if chunk.startswith("data:"):
            events.append(json.loads(chunk[5:].strip()))

    done_event = next((e for e in events if e.get("done")), None)
    assert done_event is not None
    msg = done_event.get("message", {})
    assert msg.get("tool_calls") == [{"name": "get_data"}]


@pytest.mark.asyncio
async def test_no_tool_calls_metadata_without_tools() -> None:
    """When no tools are invoked, tool_calls is absent from the message metadata."""
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
    assert metadata is None or metadata.get("tool_calls") is None


class TestMessageResponseToolCalls:
    def test_message_response_accepts_tool_calls(self) -> None:
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
            tool_calls=[{"name": "search_web"}, {"name": "search_web"}],
        )
        assert response.tool_calls is not None
        assert len(response.tool_calls) == 2
        assert response.tool_calls[0]["name"] == "search_web"

    def test_message_response_tool_calls_defaults_to_none(self) -> None:
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
        assert response.tool_calls is None
