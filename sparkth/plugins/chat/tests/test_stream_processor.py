import json
import uuid
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sparkth.lib.rag import (
    DocumentNotFoundError,
    RAGNotReadyError,
    RAGRetrievalError,
    RetrievedChunk,
)
from sparkth.plugins.chat.routes.utils.live_turns import request_stop
from sparkth.plugins.chat.routes.utils.stream_processor import ChatStreamProcessor
from sparkth.plugins.chat.schemas import ChatMessage


def _make_processor(
    messages: list[dict[str, Any]] | None = None,
    provider: Any = None,
    turn_id: str | None = None,
    user_id: int | None = None,
) -> ChatStreamProcessor:
    conversation = MagicMock()
    conversation.id = 1
    conversation.uuid = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
    service = MagicMock()
    service.add_message = AsyncMock(return_value=MagicMock(id=1))
    return ChatStreamProcessor(
        provider=provider if provider is not None else MagicMock(),
        messages=messages if messages is not None else [],
        conversation=conversation,
        service=service,
        user_id=user_id,
        turn_id=turn_id,
    )


class SimpleProvider:
    """A fake provider that streams two tokens and never asks to stop."""

    model = "test-model"

    async def stream_message(
        self, messages: list[dict[str, Any]], tools: list[Any] | None = None
    ) -> AsyncGenerator[dict[str, Any], None]:
        yield {"type": "token", "content": "Hello"}
        yield {"type": "token", "content": " world"}


def _make_chunk(
    source_name: str = "doc.pdf",
    chapter: str | None = None,
    section: str | None = "Section",
    subsection: str | None = None,
    content: str = "content",
) -> RetrievedChunk:
    return RetrievedChunk(
        source_name=source_name,
        chapter=chapter,
        section=section,
        subsection=subsection,
        content=content,
    )


class TestBuildRagContext:
    def test_section_label_subsection(self) -> None:
        processor = _make_processor()
        chunks = [_make_chunk(section="S", subsection="Sub")]
        _, sections = processor._build_rag_context(chunks)
        assert sections[0]["type"] == "subsection"

    def test_section_label_section(self) -> None:
        processor = _make_processor()
        chunks = [_make_chunk(section="S", subsection=None)]
        _, sections = processor._build_rag_context(chunks)
        assert sections[0]["type"] == "section"

    def test_section_label_chapter(self) -> None:
        processor = _make_processor()
        chunks = [_make_chunk(chapter="Ch1", section=None, subsection=None)]
        _, sections = processor._build_rag_context(chunks)
        assert sections[0]["type"] == "chapter"

    def test_deduplicates_sections(self) -> None:
        processor = _make_processor()
        chunks = [_make_chunk(section="Intro"), _make_chunk(section="Intro")]
        _, sections = processor._build_rag_context(chunks)
        assert len(sections) == 1

    def test_rag_context_contains_each_document(self) -> None:
        processor = _make_processor()
        chunks = [_make_chunk(source_name="a.pdf"), _make_chunk(source_name="b.pdf")]
        rag_context, _ = processor._build_rag_context(chunks)
        assert "[DOCUMENT CONTEXT: a.pdf]" in rag_context
        assert "[DOCUMENT CONTEXT: b.pdf]" in rag_context

    def test_section_name_joins_hierarchy(self) -> None:
        processor = _make_processor()
        chunks = [_make_chunk(chapter="Ch1", section="S1", subsection="Sub1")]
        _, sections = processor._build_rag_context(chunks)
        assert sections[0]["name"] == "Ch1 / S1 / Sub1"

    def test_section_name_general_when_no_parts(self) -> None:
        processor = _make_processor()
        chunks = [_make_chunk(chapter=None, section=None, subsection=None)]
        _, sections = processor._build_rag_context(chunks)
        assert sections[0]["name"] == "General"


class TestInjectRagIntoMessages:
    def test_replaces_drive_file_blocks(self) -> None:
        messages: list[dict[str, Any]] = [{"role": "user", "content": [{"type": "drive_file", "file_id": 1}]}]
        processor = _make_processor(messages)
        processor._inject_rag_into_messages("RAG context")
        content = messages[0]["content"]
        assert all(b.get("type") != "drive_file" for b in content)

    def test_preserves_user_text_at_end(self) -> None:
        messages: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": [
                    {"type": "drive_file", "file_id": 1},
                    {"type": "text", "text": "user question"},
                ],
            }
        ]
        processor = _make_processor(messages)
        processor._inject_rag_into_messages("context")
        content = messages[0]["content"]
        text_blocks = [b["text"] for b in content if b.get("type") == "text"]
        assert text_blocks[-1] == "user question"

    def test_skips_messages_without_drive_file(self) -> None:
        messages: list[dict[str, Any]] = [{"role": "user", "content": [{"type": "text", "text": "plain"}]}]
        processor = _make_processor(messages)
        original = list(messages[0]["content"])
        processor._inject_rag_into_messages("context")
        assert messages[0]["content"] == original

    def test_empty_rag_context_removes_drive_file_only(self) -> None:
        messages: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": [
                    {"type": "drive_file", "file_id": 1},
                    {"type": "text", "text": "question"},
                ],
            }
        ]
        processor = _make_processor(messages)
        processor._inject_rag_into_messages("")
        content = messages[0]["content"]
        assert len(content) == 1
        assert content[0]["text"] == "question"


class TestStripUnresolvedDocumentBlocks:
    def test_removes_drive_file_blocks(self) -> None:
        messages: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": [
                    {"type": "drive_file", "file_id": 1},
                    {"type": "text", "text": "hi"},
                ],
            }
        ]
        processor = _make_processor(messages)
        processor._strip_unresolved_document_blocks()
        assert all(b.get("type") != "drive_file" for b in messages[0]["content"])
        assert messages[0]["content"][0]["text"] == "hi"

    def test_leaves_string_content_unchanged(self) -> None:
        messages: list[dict[str, Any]] = [{"role": "user", "content": "Hello"}]
        processor = _make_processor(messages)
        processor._strip_unresolved_document_blocks()
        assert messages[0]["content"] == "Hello"


class TestRetrieveRagChunks:
    @pytest.mark.asyncio
    async def test_returns_chunks_on_success(self) -> None:
        processor = _make_processor()
        processor.llm = MagicMock()
        expected = [_make_chunk()]
        with patch(
            "sparkth.plugins.chat.routes.utils.stream_processor.agentic_retrieve_context",
            new_callable=AsyncMock,
        ) as mock_retrieve:
            mock_retrieve.return_value = expected
            result = await processor._retrieve_rag_chunks("query", [1], MagicMock())
        assert result == expected

    @pytest.mark.asyncio
    async def test_returns_none_on_document_not_found(self) -> None:
        processor = _make_processor()
        processor.llm = MagicMock()
        with patch(
            "sparkth.plugins.chat.routes.utils.stream_processor.agentic_retrieve_context",
            new_callable=AsyncMock,
        ) as mock_retrieve:
            mock_retrieve.side_effect = DocumentNotFoundError()
            result = await processor._retrieve_rag_chunks("query", [1], MagicMock())
        assert result is None

    @pytest.mark.asyncio
    async def test_persists_error_on_document_not_found(self) -> None:
        processor = _make_processor()
        processor.llm = MagicMock()
        bg_session = MagicMock()
        with patch(
            "sparkth.plugins.chat.routes.utils.stream_processor.agentic_retrieve_context",
            new_callable=AsyncMock,
        ) as mock_retrieve:
            mock_retrieve.side_effect = DocumentNotFoundError()
            await processor._retrieve_rag_chunks("query", [1], bg_session)
        processor.service.add_message.assert_called_once()  # type: ignore[attr-defined]
        assert processor.service.add_message.call_args.kwargs["is_error"] is True  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_returns_none_on_rag_not_ready(self) -> None:
        processor = _make_processor()
        processor.llm = MagicMock()
        with patch(
            "sparkth.plugins.chat.routes.utils.stream_processor.agentic_retrieve_context",
            new_callable=AsyncMock,
        ) as mock_retrieve:
            mock_retrieve.side_effect = RAGNotReadyError(1, "PENDING")
            result = await processor._retrieve_rag_chunks("query", [1], MagicMock())
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_retrieval_error(self) -> None:
        processor = _make_processor()
        processor.llm = MagicMock()
        with patch(
            "sparkth.plugins.chat.routes.utils.stream_processor.agentic_retrieve_context",
            new_callable=AsyncMock,
        ) as mock_retrieve:
            mock_retrieve.side_effect = RAGRetrievalError()
            result = await processor._retrieve_rag_chunks("query", [1], MagicMock())
        assert result is None

    @pytest.mark.asyncio
    async def test_persists_error_on_rag_not_ready(self) -> None:
        processor = _make_processor()
        processor.llm = MagicMock()
        bg_session = MagicMock()
        with patch(
            "sparkth.plugins.chat.routes.utils.stream_processor.agentic_retrieve_context",
            new_callable=AsyncMock,
        ) as mock_retrieve:
            mock_retrieve.side_effect = RAGNotReadyError(1, "PENDING")
            await processor._retrieve_rag_chunks("query", [1], bg_session)
        processor.service.add_message.assert_called_once()  # type: ignore[attr-defined]
        assert processor.service.add_message.call_args.kwargs["is_error"] is True  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_persists_error_on_retrieval_error(self) -> None:
        processor = _make_processor()
        processor.llm = MagicMock()
        bg_session = MagicMock()
        with patch(
            "sparkth.plugins.chat.routes.utils.stream_processor.agentic_retrieve_context",
            new_callable=AsyncMock,
        ) as mock_retrieve:
            mock_retrieve.side_effect = RAGRetrievalError()
            await processor._retrieve_rag_chunks("query", [1], bg_session)
        processor.service.add_message.assert_called_once()  # type: ignore[attr-defined]
        assert processor.service.add_message.call_args.kwargs["is_error"] is True  # type: ignore[attr-defined]


class TestRunRagPhase:
    @pytest.mark.asyncio
    async def test_returns_empty_list_when_rag_disabled(self) -> None:
        processor = _make_processor()
        processor.rag_search_required = False
        result = await processor._run_rag_phase(MagicMock())
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_unresolved_messages(self) -> None:
        processor = _make_processor()
        processor.rag_search_required = True
        processor.unresolved_messages = None
        result = await processor._run_rag_phase(MagicMock())
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_none_when_retrieval_fails(self) -> None:
        processor = _make_processor()
        processor.rag_search_required = True
        processor.user_id = 1
        processor.llm = MagicMock()
        processor.unresolved_messages = [ChatMessage(role="user", content=[{"type": "drive_file", "file_id": 1}])]
        with patch(
            "sparkth.plugins.chat.routes.utils.stream_processor.agentic_retrieve_context",
            new_callable=AsyncMock,
        ) as mock_retrieve:
            mock_retrieve.side_effect = DocumentNotFoundError()
            result = await processor._run_rag_phase(MagicMock())
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_sections_on_success(self) -> None:
        processor = _make_processor(messages=[{"role": "user", "content": [{"type": "drive_file", "file_id": 1}]}])
        processor.rag_search_required = True
        processor.user_id = 1
        processor.llm = MagicMock()
        processor.unresolved_messages = [ChatMessage(role="user", content=[{"type": "drive_file", "file_id": 1}])]
        with patch(
            "sparkth.plugins.chat.routes.utils.stream_processor.agentic_retrieve_context",
            new_callable=AsyncMock,
        ) as mock_retrieve:
            mock_retrieve.return_value = [_make_chunk(section="Intro")]
            result = await processor._run_rag_phase(MagicMock())
        assert result is not None
        assert len(result) == 1
        assert result[0]["name"] == "Intro"


class TestCollectStreamResponse:
    @pytest.mark.asyncio
    async def test_returns_full_response_and_empty_tool_calls(self) -> None:
        processor = _make_processor()

        async def stream_gen(*args: object, **kwargs: object) -> object:
            yield {"type": "token", "content": "Hello"}
            yield {"type": "token", "content": " world"}

        processor.provider.stream_message = stream_gen  # type: ignore[assignment]
        result = await processor._collect_stream_response(MagicMock())
        assert result is not None
        full_response, tool_calls, stopped = result
        assert full_response == "Hello world"
        assert tool_calls == []
        assert stopped is False

    @pytest.mark.asyncio
    async def test_collects_tool_call_names(self) -> None:
        processor = _make_processor()

        async def stream_gen(*args: object, **kwargs: object) -> object:
            yield {"type": "tool_start", "name": "search_web"}
            yield {"type": "tool_end", "name": "search_web"}
            yield {"type": "token", "content": "Done"}

        processor.provider.stream_message = stream_gen  # type: ignore[assignment]
        result = await processor._collect_stream_response(MagicMock())
        assert result is not None
        _, tool_calls, stopped = result
        assert tool_calls == [{"name": "search_web"}]
        assert stopped is False

    @pytest.mark.asyncio
    async def test_returns_none_on_provider_api_error(self) -> None:
        import httpx

        processor = _make_processor()

        async def stream_gen(*args: object, **kwargs: object) -> object:
            if False:
                yield {}
            raise httpx.RemoteProtocolError("connection reset by peer")

        processor.provider.stream_message = stream_gen  # type: ignore[assignment]
        result = await processor._collect_stream_response(MagicMock())
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_os_error(self) -> None:
        processor = _make_processor()

        async def stream_gen(*args: object, **kwargs: object) -> object:
            if False:
                yield {}
            raise OSError("connection reset")

        processor.provider.stream_message = stream_gen  # type: ignore[assignment]
        result = await processor._collect_stream_response(MagicMock())
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_langchain_exception(self) -> None:
        from langchain_core.exceptions import OutputParserException

        processor = _make_processor()

        async def stream_gen(*args: object, **kwargs: object) -> object:
            if False:
                yield {}
            raise OutputParserException("parse failed")

        processor.provider.stream_message = stream_gen  # type: ignore[assignment]
        result = await processor._collect_stream_response(MagicMock())
        assert result is None


class TestPersistAndEmitDone:
    @pytest.mark.asyncio
    async def test_calls_add_message_with_rag_sections_in_metadata(self) -> None:
        processor = _make_processor()
        sections: list[dict[str, str | None]] = [{"type": "section", "name": "Intro", "source": "doc.pdf"}]
        await processor._persist_and_emit_done("response", sections, [], MagicMock())
        call_kwargs = processor.service.add_message.call_args.kwargs  # type: ignore[attr-defined]
        assert call_kwargs["metadata"]["rag_sections"] == sections

    @pytest.mark.asyncio
    async def test_calls_add_message_with_tool_calls_in_metadata(self) -> None:
        processor = _make_processor()
        tool_calls = [{"name": "search_web"}]
        await processor._persist_and_emit_done("response", [], tool_calls, MagicMock())
        call_kwargs = processor.service.add_message.call_args.kwargs  # type: ignore[attr-defined]
        assert call_kwargs["metadata"]["tool_calls"] == tool_calls

    @pytest.mark.asyncio
    async def test_calls_add_message_without_metadata_when_none(self) -> None:
        processor = _make_processor()
        await processor._persist_and_emit_done("response", [], [], MagicMock())
        call_kwargs = processor.service.add_message.call_args.kwargs  # type: ignore[attr-defined]
        assert call_kwargs.get("metadata") is None

    @pytest.mark.asyncio
    async def test_enqueues_done_event(self) -> None:
        import json

        processor = _make_processor()
        await processor._persist_and_emit_done("Hello", [], [], MagicMock())
        payload = await processor.queue.get()
        assert payload is not None
        data = json.loads(payload)
        assert data["done"] is True
        assert data["token"] == ""
        assert data["conversation_id"] == str(processor.conversation_uuid)


class TestStopHonoured:
    @pytest.mark.asyncio
    async def test_a_stopped_turn_runs_no_further_tools(self) -> None:
        """The stop lands between events, so the first tool completes and the second never starts."""
        executed: list[str] = []

        class StoppingProvider:
            model = "test-model"

            async def stream_message(
                self, messages: list[dict[str, Any]], tools: list[Any] | None = None
            ) -> AsyncGenerator[dict[str, Any], None]:
                yield {"type": "tool_start", "name": "first_tool"}
                executed.append("first_tool")
                yield {"type": "tool_end", "name": "first_tool"}
                request_stop("turn-1", 1)
                yield {"type": "tool_start", "name": "second_tool"}
                executed.append("second_tool")
                yield {"type": "tool_end", "name": "second_tool"}
                yield {"type": "token", "content": "done"}

        processor = _make_processor(provider=StoppingProvider(), turn_id="turn-1", user_id=1)

        payloads = [json.loads(chunk.removeprefix("data: ")) async for chunk in processor.stream()]

        assert executed == ["first_tool"]
        done = payloads[-1]
        assert done["done"] is True
        assert done["stopped"] is True
        assert done["message"]["tool_calls"] == [{"name": "first_tool"}]

    @pytest.mark.asyncio
    async def test_a_stop_during_execution_still_keeps_the_finishing_tool(self) -> None:
        """Stop requested while a tool is executing (between its tool_start and tool_end): the
        in-flight tool's result is still kept, and only the next tool is skipped."""
        executed: list[str] = []

        class StoppingDuringExecutionProvider:
            model = "test-model"

            async def stream_message(
                self, messages: list[dict[str, Any]], tools: list[Any] | None = None
            ) -> AsyncGenerator[dict[str, Any], None]:
                yield {"type": "tool_start", "name": "first_tool"}
                # The stop lands here — inside the window where the real provider is
                # awaiting `_execute_tool`, between yielding tool_start and tool_end.
                request_stop("turn-6", 1)
                executed.append("first_tool")
                yield {"type": "tool_end", "name": "first_tool"}
                yield {"type": "tool_start", "name": "second_tool"}
                executed.append("second_tool")
                yield {"type": "tool_end", "name": "second_tool"}
                yield {"type": "token", "content": "done"}

        processor = _make_processor(provider=StoppingDuringExecutionProvider(), turn_id="turn-6", user_id=1)

        payloads = [json.loads(chunk.removeprefix("data: ")) async for chunk in processor.stream()]

        assert executed == ["first_tool"]
        done = payloads[-1]
        assert done["stopped"] is True
        assert done["message"]["tool_calls"] == [{"name": "first_tool"}]

    @pytest.mark.asyncio
    async def test_a_stopped_turn_keeps_the_token_delivered_when_stop_was_noticed(self) -> None:
        """A token is always text the model already produced, never work in flight, so the one
        delivered on the very iteration the stop is noticed is kept, not dropped. The fourth
        token is load-bearing: with only three, the test would pass even without the
        ``if stopping: break`` — the generator would just run out on its own. A fourth token
        that must never be requested is what a deleted break would let leak through.
        """

        class StoppingProvider:
            model = "test-model"

            async def stream_message(
                self, messages: list[dict[str, Any]], tools: list[Any] | None = None
            ) -> AsyncGenerator[dict[str, Any], None]:
                yield {"type": "token", "content": "Half a "}
                yield {"type": "token", "content": "sentence"}
                request_stop("turn-2", 1)
                yield {"type": "token", "content": " that still arrives"}
                yield {"type": "token", "content": " but this one never does"}

        processor = _make_processor(provider=StoppingProvider(), turn_id="turn-2", user_id=1)

        payloads = [json.loads(chunk.removeprefix("data: ")) async for chunk in processor.stream()]

        done = payloads[-1]
        assert done["message"]["content"] == "Half a sentence that still arrives"
        assert done["stopped"] is True

    @pytest.mark.asyncio
    async def test_an_uninterrupted_turn_is_not_marked_stopped(self) -> None:
        processor = _make_processor(provider=SimpleProvider(), turn_id="turn-3", user_id=1)

        payloads = [json.loads(chunk.removeprefix("data: ")) async for chunk in processor.stream()]

        assert payloads[-1].get("stopped", False) is False

    @pytest.mark.asyncio
    async def test_release_turn_called_when_stream_ends(self) -> None:
        """The turn is released from the live-turns registry once the stream finishes."""
        processor = _make_processor(provider=SimpleProvider(), turn_id="turn-4", user_id=1)

        async for _ in processor.stream():
            pass

        assert request_stop("turn-4", 1) is False

    @pytest.mark.asyncio
    async def test_a_turn_is_not_registered_until_its_stream_runs(self) -> None:
        """Registering inside the stream is what keeps a turn whose stream never runs out of
        the registry: there is nothing to release, so nothing can be left behind."""
        _make_processor(provider=SimpleProvider(), turn_id="turn-7", user_id=1)

        assert request_stop("turn-7", 1) is False
