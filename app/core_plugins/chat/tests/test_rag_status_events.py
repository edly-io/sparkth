"""Tests for SSE status events during RAG retrieval."""

import asyncio
import inspect
import json
import uuid
from datetime import datetime
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core_plugins.chat.routes.completions import stream_chat_response
from app.core_plugins.chat.routes.helpers import parse_metadata_list
from app.core_plugins.chat.schemas import ChatCompletionRequest, ChatMessage, MessageResponse
from app.lib.rag import (
    DocumentNotFoundError,
    RAGNotReadyError,
    RAGRetrievalError,
    RetrievedChunk,
)


def _make_chunk(
    content: str = "Content here.",
    source_name: str = "doc.pdf",
    chapter: str | None = None,
    section: str | None = "Content",
    subsection: str | None = None,
) -> RetrievedChunk:
    return RetrievedChunk(
        source_name=source_name,
        chapter=chapter,
        section=section,
        subsection=subsection,
        content=content,
    )


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
    conv.uuid = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
    return conv


def _unresolved_with_file(file_id: int = 1) -> list[ChatMessage]:
    return [ChatMessage(role="user", content=[{"type": "drive_file", "file_id": file_id}])]


async def _collect_events(gen: AsyncGenerator[str, None]) -> list[dict]:  # type: ignore[type-arg]
    events = []
    async for chunk in gen:
        if chunk.startswith("data:"):
            events.append(json.loads(chunk.replace("data: ", "").strip()))
    return events


@pytest.mark.asyncio
async def test_status_events_emitted_before_tokens() -> None:
    chunks = [_make_chunk("Content here.", source_name="doc.pdf", section="Content")]

    unresolved = [
        ChatMessage(
            role="user", content=[{"type": "drive_file", "file_id": 42}, {"type": "text", "text": "Create a course"}]
        )
    ]

    with (
        patch(
            "app.core_plugins.chat.routes.completions.agentic_retrieve_context", new_callable=AsyncMock
        ) as mock_retrieve,
    ):
        mock_retrieve.return_value = chunks
        events = []
        async for chunk in stream_chat_response(
            provider=_make_provider(),
            messages=[{"role": "user", "content": [{"type": "drive_file", "file_id": 42}]}],
            conversation=_make_conversation(),
            service=_make_service(),
            tools=None,
            unresolved_messages=unresolved,
            user_id=1,
            llm=MagicMock(),
            should_run_rag=True,
        ):
            events.append(chunk)

    # Parse SSE events
    parsed = []
    for event in events:
        if event.startswith("data:"):
            parsed.append(json.loads(event.replace("data: ", "").strip()))

    statuses = [e for e in parsed if "status" in e]
    status_names = [e["status"] for e in statuses]

    # Single searching_documents event (not per-file searching_document)
    assert "searching_documents" in status_names
    assert "searching_document" not in status_names
    assert "generating" in status_names

    # Status events must precede token events
    first_status_idx = next(i for i, e in enumerate(parsed) if "status" in e)
    first_token_idx = next((i for i, e in enumerate(parsed) if "token" in e and not e.get("done")), len(parsed))
    assert first_status_idx < first_token_idx


@pytest.mark.asyncio
async def test_searching_documents_event_includes_file_count() -> None:
    """The searching_documents status event includes a file_count field."""
    chunks = [_make_chunk("Content.", source_name="doc.pdf")]

    unresolved = [
        ChatMessage(
            role="user",
            content=[
                {"type": "drive_file", "file_id": 1},
                {"type": "drive_file", "file_id": 2},
                {"type": "text", "text": "Query"},
            ],
        )
    ]

    with (
        patch(
            "app.core_plugins.chat.routes.completions.agentic_retrieve_context", new_callable=AsyncMock
        ) as mock_retrieve,
    ):
        mock_retrieve.return_value = chunks
        events = []
        async for chunk in stream_chat_response(
            provider=_make_provider(),
            messages=[{"role": "user", "content": [{"type": "drive_file", "file_id": 1}]}],
            conversation=_make_conversation(),
            service=_make_service(),
            tools=None,
            unresolved_messages=unresolved,
            user_id=1,
            llm=MagicMock(),
            should_run_rag=True,
        ):
            events.append(chunk)

    parsed = [json.loads(e.replace("data: ", "").strip()) for e in events if e.startswith("data:")]
    searching_event = next((e for e in parsed if e.get("status") == "searching_documents"), None)
    assert searching_event is not None
    assert searching_event["file_count"] == 2


@pytest.mark.asyncio
async def test_agent_context_injected_into_messages() -> None:
    """Agent-retrieved context is injected into messages before the LLM call."""
    chunks = [_make_chunk("Data privacy content.", source_name="doc.pdf", section="Data Privacy")]

    original_messages = [{"role": "user", "content": [{"type": "drive_file", "file_id": 1}]}]
    unresolved = [ChatMessage(role="user", content=[{"type": "drive_file", "file_id": 1}])]

    with (
        patch(
            "app.core_plugins.chat.routes.completions.agentic_retrieve_context", new_callable=AsyncMock
        ) as mock_retrieve,
    ):
        mock_retrieve.return_value = chunks
        async for _ in stream_chat_response(
            provider=_make_provider(),
            messages=original_messages,
            conversation=_make_conversation(),
            service=_make_service(),
            tools=None,
            unresolved_messages=unresolved,
            user_id=1,
            llm=MagicMock(),
            should_run_rag=True,
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
    chunks = [
        _make_chunk("Context from file 1.", source_name="file1.pdf", section="Section"),
        _make_chunk("Context from file 2.", source_name="file2.pdf", section="Section"),
    ]

    original_messages = [
        {"role": "user", "content": [{"type": "drive_file", "file_id": 1}, {"type": "drive_file", "file_id": 2}]}
    ]
    unresolved = [
        ChatMessage(
            role="user",
            content=[{"type": "drive_file", "file_id": 1}, {"type": "drive_file", "file_id": 2}],
        )
    ]

    with (
        patch(
            "app.core_plugins.chat.routes.completions.agentic_retrieve_context", new_callable=AsyncMock
        ) as mock_retrieve,
    ):
        mock_retrieve.return_value = chunks
        async for _ in stream_chat_response(
            provider=_make_provider(),
            messages=original_messages,
            conversation=_make_conversation(),
            service=_make_service(),
            tools=None,
            unresolved_messages=unresolved,
            user_id=1,
            llm=MagicMock(),
            should_run_rag=True,
        ):
            pass

    content = original_messages[0]["content"]
    assert isinstance(content, list)
    text_blocks = [b["text"] for b in content if isinstance(b, dict) and b.get("type") == "text"]
    # context prompt + two RAG context blocks (one per source) — neither file's context is lost
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
    chunks = [
        _make_chunk("Intro content", source_name="guide.pdf", section="Introduction"),
        _make_chunk("Conclusion content", source_name="guide.pdf", section="Conclusion"),
    ]

    unresolved = [ChatMessage(role="user", content=[{"type": "drive_file", "file_id": 1}])]
    service = _make_service()

    with (
        patch(
            "app.core_plugins.chat.routes.completions.agentic_retrieve_context", new_callable=AsyncMock
        ) as mock_retrieve,
    ):
        mock_retrieve.return_value = chunks
        async for _ in stream_chat_response(
            provider=_make_provider(),
            messages=[{"role": "user", "content": [{"type": "drive_file", "file_id": 1}]}],
            conversation=_make_conversation(),
            service=service,
            tools=None,
            unresolved_messages=unresolved,
            user_id=1,
            llm=MagicMock(),
            should_run_rag=True,
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


# RAG exception → user-friendly SSE error (non-empty string)


@pytest.mark.asyncio
async def test_drive_file_not_found_emits_friendly_error() -> None:
    with (
        patch(
            "app.core_plugins.chat.routes.completions.agentic_retrieve_context", new_callable=AsyncMock
        ) as mock_retrieve,
    ):
        mock_retrieve.side_effect = DocumentNotFoundError()
        events = await _collect_events(
            stream_chat_response(
                provider=_make_provider(),
                messages=[{"role": "user", "content": [{"type": "drive_file", "file_id": 1}]}],
                conversation=_make_conversation(),
                service=_make_service(),
                tools=None,
                unresolved_messages=_unresolved_with_file(),
                user_id=1,
                llm=MagicMock(),
                should_run_rag=True,
            )
        )

    error_events = [e for e in events if "error" in e]
    assert len(error_events) == 1
    assert error_events[0]["error"] != ""
    assert "found" in error_events[0]["error"].lower() or "accessible" in error_events[0]["error"].lower()
    assert error_events[0]["done"] is True


@pytest.mark.asyncio
async def test_rag_not_ready_emits_friendly_error() -> None:
    with (
        patch(
            "app.core_plugins.chat.routes.completions.agentic_retrieve_context", new_callable=AsyncMock
        ) as mock_retrieve,
    ):
        mock_retrieve.side_effect = RAGNotReadyError(1, "PENDING")
        events = await _collect_events(
            stream_chat_response(
                provider=_make_provider(),
                messages=[{"role": "user", "content": [{"type": "drive_file", "file_id": 1}]}],
                conversation=_make_conversation(),
                service=_make_service(),
                tools=None,
                unresolved_messages=_unresolved_with_file(),
                user_id=1,
                llm=MagicMock(),
                should_run_rag=True,
            )
        )

    error_events = [e for e in events if "error" in e]
    assert len(error_events) == 1
    assert error_events[0]["error"] != ""
    assert "processed" in error_events[0]["error"].lower() or "wait" in error_events[0]["error"].lower()
    assert error_events[0]["done"] is True


@pytest.mark.asyncio
async def test_rag_retrieval_error_emits_friendly_error() -> None:
    with (
        patch(
            "app.core_plugins.chat.routes.completions.agentic_retrieve_context", new_callable=AsyncMock
        ) as mock_retrieve,
    ):
        mock_retrieve.side_effect = RAGRetrievalError()
        events = await _collect_events(
            stream_chat_response(
                provider=_make_provider(),
                messages=[{"role": "user", "content": [{"type": "drive_file", "file_id": 1}]}],
                conversation=_make_conversation(),
                service=_make_service(),
                tools=None,
                unresolved_messages=_unresolved_with_file(),
                user_id=1,
                llm=MagicMock(),
                should_run_rag=True,
            )
        )

    error_events = [e for e in events if "error" in e]
    assert len(error_events) == 1
    assert error_events[0]["error"] != ""
    assert "search" in error_events[0]["error"].lower() or "failed" in error_events[0]["error"].lower()
    assert error_events[0]["done"] is True


# Background task: add_message is called even when consumer stops early


@pytest.mark.asyncio
async def test_add_message_called_after_early_consumer_exit() -> None:
    """DB write must happen even if the SSE consumer stops reading before done."""
    service = _make_service()

    task_holder: list[asyncio.Task[None]] = []
    gen = stream_chat_response(
        provider=_make_provider(),
        messages=[{"role": "user", "content": "Hello"}],
        conversation=_make_conversation(),
        service=service,
        tools=None,
        _task_holder=task_holder,
    )

    # Consume only the first event then abandon the generator
    async for _ in gen:
        break

    await task_holder[0]

    add_message_calls = service.add_message.call_args_list
    assistant_call = next((c for c in add_message_calls if c.kwargs.get("role") == "assistant"), None)
    assert assistant_call is not None, "add_message must be called even when the consumer exits early"


# RAG exception → error message persisted to DB (is_error=True)


@pytest.mark.asyncio
async def test_drive_file_not_found_persists_error_to_db() -> None:
    """DocumentNotFoundError must write an is_error=True message to DB."""
    service = _make_service()
    task_holder: list[asyncio.Task[None]] = []
    with (
        patch(
            "app.core_plugins.chat.routes.completions.agentic_retrieve_context", new_callable=AsyncMock
        ) as mock_retrieve,
    ):
        mock_retrieve.side_effect = DocumentNotFoundError()
        gen = stream_chat_response(
            provider=_make_provider(),
            messages=[{"role": "user", "content": [{"type": "drive_file", "file_id": 1}]}],
            conversation=_make_conversation(),
            service=service,
            tools=None,
            unresolved_messages=_unresolved_with_file(),
            user_id=1,
            llm=MagicMock(),
            should_run_rag=True,
            _task_holder=task_holder,
        )
        async for _ in gen:
            pass
    await task_holder[0]
    error_calls = [c for c in service.add_message.call_args_list if c.kwargs.get("is_error") is True]
    assert len(error_calls) == 1
    assert (
        "found" in error_calls[0].kwargs["content"].lower() or "accessible" in error_calls[0].kwargs["content"].lower()
    )


@pytest.mark.asyncio
async def test_rag_not_ready_persists_error_to_db() -> None:
    """RAGNotReadyError must write an is_error=True message to DB."""
    service = _make_service()
    task_holder: list[asyncio.Task[None]] = []
    with (
        patch(
            "app.core_plugins.chat.routes.completions.agentic_retrieve_context", new_callable=AsyncMock
        ) as mock_retrieve,
    ):
        mock_retrieve.side_effect = RAGNotReadyError(1, "PENDING")
        gen = stream_chat_response(
            provider=_make_provider(),
            messages=[{"role": "user", "content": [{"type": "drive_file", "file_id": 1}]}],
            conversation=_make_conversation(),
            service=service,
            tools=None,
            unresolved_messages=_unresolved_with_file(),
            user_id=1,
            llm=MagicMock(),
            should_run_rag=True,
            _task_holder=task_holder,
        )
        async for _ in gen:
            pass
    await task_holder[0]
    error_calls = [c for c in service.add_message.call_args_list if c.kwargs.get("is_error") is True]
    assert len(error_calls) == 1
    assert "processed" in error_calls[0].kwargs["content"].lower() or "wait" in error_calls[0].kwargs["content"].lower()


@pytest.mark.asyncio
async def test_rag_retrieval_error_persists_error_to_db() -> None:
    """RAGRetrievalError must write an is_error=True message to DB."""
    service = _make_service()
    task_holder: list[asyncio.Task[None]] = []
    with (
        patch(
            "app.core_plugins.chat.routes.completions.agentic_retrieve_context", new_callable=AsyncMock
        ) as mock_retrieve,
    ):
        mock_retrieve.side_effect = RAGRetrievalError()
        gen = stream_chat_response(
            provider=_make_provider(),
            messages=[{"role": "user", "content": [{"type": "drive_file", "file_id": 1}]}],
            conversation=_make_conversation(),
            service=service,
            tools=None,
            unresolved_messages=_unresolved_with_file(),
            user_id=1,
            llm=MagicMock(),
            should_run_rag=True,
            _task_holder=task_holder,
        )
        async for _ in gen:
            pass
    await task_holder[0]
    error_calls = [c for c in service.add_message.call_args_list if c.kwargs.get("is_error") is True]
    assert len(error_calls) == 1
    assert "search" in error_calls[0].kwargs["content"].lower() or "failed" in error_calls[0].kwargs["content"].lower()


@pytest.mark.asyncio
async def test_unexpected_error_persists_error_to_db() -> None:
    """An unhandled exception escaping _run must write an is_error=True message to DB."""
    service = _make_service()

    provider = MagicMock()

    async def _failing_stream(*_args: object, **_kwargs: object) -> AsyncGenerator[str, None]:
        if False:
            yield ""  # makes this an async generator
        raise RuntimeError("simulated unexpected failure")

    provider.stream_message = _failing_stream

    task_holder: list[asyncio.Task[None]] = []
    gen = stream_chat_response(
        provider=provider,
        messages=[{"role": "user", "content": "Hello"}],
        conversation=_make_conversation(),
        service=service,
        tools=None,
        _task_holder=task_holder,
    )
    async for _ in gen:
        pass
    await task_holder[0]

    error_calls = [c for c in service.add_message.call_args_list if c.kwargs.get("is_error") is True]
    assert len(error_calls) == 1
    assert "unexpected" in error_calls[0].kwargs["content"].lower()


# Metadata parsing helper


class TestParseMetadataList:
    def test_returns_none_for_no_metadata(self) -> None:
        assert parse_metadata_list(None, "tool_calls") is None

    def test_returns_none_for_empty_metadata(self) -> None:
        assert parse_metadata_list("{}", "tool_calls") is None

    def test_returns_none_for_invalid_json(self) -> None:
        assert parse_metadata_list("not-json", "tool_calls") is None

    def test_returns_none_when_value_not_list(self) -> None:
        assert parse_metadata_list(json.dumps({"tool_calls": "bad"}), "tool_calls") is None

    def test_returns_list_for_tool_calls_key(self) -> None:
        meta = json.dumps({"tool_calls": [{"name": "search_web"}, {"name": "search_web"}]})
        result = parse_metadata_list(meta, "tool_calls")
        assert result is not None
        assert len(result) == 2
        assert result[0]["name"] == "search_web"

    def test_returns_list_for_rag_sections_key(self) -> None:
        meta = json.dumps({"rag_sections": [{"type": "section", "name": "Intro"}]})
        result = parse_metadata_list(meta, "rag_sections")
        assert result is not None
        assert len(result) == 1
        assert result[0]["name"] == "Intro"

    def test_ignores_other_keys(self) -> None:
        meta = json.dumps({"rag_sections": [{"type": "section", "name": "Intro"}]})
        assert parse_metadata_list(meta, "tool_calls") is None


# Tool-call streaming → metadata persistence + done payload


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

    task_holder: list[asyncio.Task[None]] = []
    async for _ in stream_chat_response(
        provider=provider,
        messages=[{"role": "user", "content": "search for something"}],
        conversation=_make_conversation(),
        service=service,
        tools=None,
        _task_holder=task_holder,
    ):
        pass
    await task_holder[0]

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
    task_holder: list[asyncio.Task[None]] = []
    async for chunk in stream_chat_response(
        provider=provider,
        messages=[{"role": "user", "content": "run a tool"}],
        conversation=_make_conversation(),
        service=_make_service(),
        tools=None,
        _task_holder=task_holder,
    ):
        if chunk.startswith("data:"):
            events.append(json.loads(chunk[5:].strip()))
    await task_holder[0]

    done_event = next((e for e in events if e.get("done")), None)
    assert done_event is not None
    msg = done_event.get("message", {})
    assert msg.get("tool_calls") == [{"name": "get_data"}]


@pytest.mark.asyncio
async def test_no_tool_calls_metadata_without_tools() -> None:
    """When no tools are invoked, tool_calls is absent from the message metadata."""
    service = _make_service()

    task_holder: list[asyncio.Task[None]] = []
    async for _ in stream_chat_response(
        provider=_make_provider(),
        messages=[{"role": "user", "content": "Hello"}],
        conversation=_make_conversation(),
        service=service,
        tools=None,
        _task_holder=task_holder,
    ):
        pass
    await task_holder[0]

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


class TestSimilarityThresholdRemoved:
    def test_chat_completion_request_has_no_similarity_threshold(self) -> None:
        """similarity_threshold field must be removed from ChatCompletionRequest."""
        # The field must not be present in the model's fields
        assert "similarity_threshold" not in ChatCompletionRequest.model_fields

    def test_chat_completion_request_accepts_valid_fields(self) -> None:
        """ChatCompletionRequest still works without similarity_threshold."""
        req = ChatCompletionRequest(
            llm_config_id=1,
            messages=[ChatMessage(role="user", content="hello")],
        )
        assert req.llm_config_id == 1

    def test_stream_chat_response_has_no_similarity_threshold_param(self) -> None:
        """stream_chat_response must not have a similarity_threshold parameter."""
        sig = inspect.signature(stream_chat_response)
        assert "similarity_threshold" not in sig.parameters
