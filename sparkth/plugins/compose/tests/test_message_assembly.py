"""Tests for building the message list a provider is sent.

Three things get combined: the conversation's stored history, the turns the request carried, and —
when retrieval is going to run — a synthetic turn of document references for it to resolve. The
route did this inline and nothing exercised it directly, so the cases below are asserted here for
the first time: which end of the history is replaced, and what the provider receives in each of the
streaming, non-streaming and no-retrieval shapes.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sparkth.lib.documents import Document, DocumentStatus
from sparkth.plugins.compose.constants import ATTACHED_DOCUMENTS_HEADING
from sparkth.plugins.compose.models import Message
from sparkth.plugins.compose.routes.utils.message_assembly import assemble_provider_messages
from sparkth.plugins.compose.schemas import ChatCompletionRequest, ChatMessage, UploadedFile

_RESOLVE = "sparkth.plugins.compose.routes.utils.message_assembly.resolve_document_blocks"


def _request(*contents: str | list[dict[str, Any]], stream: bool = False) -> ChatCompletionRequest:
    return ChatCompletionRequest(
        llm_config_id=1,
        messages=[ChatMessage(role="user", content=c) for c in contents],
        stream=stream,
    )


def _stored(role: str, content: str) -> Message:
    return Message(conversation_id=1, role=role, content=content)


def _document(document_id: int = 1, name: str = "textbook.pdf") -> Document:
    return Document(id=document_id, user_id=1, name=name, status=DocumentStatus.READY)


class TestHistoryAndCurrentTurns:
    """Stored history leads, and the request's own turns replace their stored copies."""

    @pytest.mark.asyncio
    async def test_stored_history_precedes_the_current_turn(self) -> None:
        request = _request("what about chapter 3?")
        db_messages = [
            _stored("user", "hello"),
            _stored("assistant", "hi"),
            _stored("user", "what about chapter 3?"),
        ]

        messages, _unresolved = await assemble_provider_messages(
            request,
            db_messages,
            [],
            "",
            False,
            MagicMock(),
            uploaded_files=[],
            analytics=MagicMock(),
            listed_documents=[],
        )

        assert [m["content"] for m in messages] == ["hello", "hi", "what about chapter 3?"]

    @pytest.mark.asyncio
    async def test_the_current_turns_come_from_the_request_not_the_database(self) -> None:
        """The stored copy of this turn is flattened text; the request still has its content
        blocks, and retrieval needs those."""
        blocks: list[dict[str, Any]] = [{"type": "text", "text": "summarise this"}]
        request = _request(blocks)
        db_messages = [_stored("user", "summarise this")]

        messages, _unresolved = await assemble_provider_messages(
            request,
            db_messages,
            [],
            "",
            False,
            MagicMock(),
            uploaded_files=[],
            analytics=MagicMock(),
            listed_documents=[],
        )

        assert messages[-1]["content"] == blocks

    @pytest.mark.asyncio
    async def test_a_conversation_with_no_prior_turns_sends_only_the_request(self) -> None:
        request = _request("first message")

        messages, _unresolved = await assemble_provider_messages(
            request,
            [_stored("user", "first message")],
            [],
            "",
            False,
            MagicMock(),
            uploaded_files=[],
            analytics=MagicMock(),
            listed_documents=[],
        )

        assert [m["content"] for m in messages] == ["first message"]

    @pytest.mark.asyncio
    async def test_uploaded_files_come_between_the_history_and_the_current_turn(self) -> None:
        request = _request("summarise them")
        uploaded_files = [
            UploadedFile(name="a.txt", text="alpha"),
            UploadedFile(name="b.txt", text="beta"),
        ]
        db_messages = [_stored("user", "hello"), _stored("assistant", "hi"), _stored("user", "summarise them")]

        messages, _unresolved = await assemble_provider_messages(
            request,
            db_messages,
            [],
            "",
            False,
            MagicMock(),
            uploaded_files=uploaded_files,
            analytics=MagicMock(),
            listed_documents=[],
        )

        assert [m["content"] for m in messages] == [
            "hello",
            "hi",
            "[File: a.txt]\n\nalpha",
            "[File: b.txt]\n\nbeta",
            "summarise them",
        ]


class TestWhenRetrievalWillRun:
    """A synthetic turn carries the document references retrieval resolves."""

    @pytest.mark.asyncio
    async def test_streaming_sends_the_references_unresolved(self) -> None:
        """The stream resolves them itself, so the provider list keeps the reference blocks."""
        request = _request("what powers a cell?", stream=True)

        messages, unresolved = await assemble_provider_messages(
            request,
            [],
            [_document(7)],
            "what powers a cell?",
            True,
            MagicMock(),
            uploaded_files=[],
            analytics=MagicMock(),
            listed_documents=[],
        )

        assert unresolved is not None
        blocks = messages[-1]["content"]
        assert {"type": "drive_file", "file_id": 7} in blocks
        assert {"type": "text", "text": "what powers a cell?"} in blocks

    @pytest.mark.asyncio
    async def test_non_streaming_resolves_the_references_first(self) -> None:
        """There is no stream to do it in, so retrieval runs here and the provider sees context."""
        request = _request("what powers a cell?")
        resolved = [ChatMessage(role="user", content=[{"type": "text", "text": "[DOCUMENT CONTEXT] mitochondria"}])]

        with patch(_RESOLVE, new_callable=AsyncMock, return_value=resolved) as mock_resolve:
            messages, unresolved = await assemble_provider_messages(
                request,
                [],
                [_document(7)],
                "what powers a cell?",
                True,
                MagicMock(),
                uploaded_files=[],
                analytics=MagicMock(),
                listed_documents=[],
            )

        mock_resolve.assert_awaited_once()
        assert messages[-1]["content"] == resolved[0].content
        assert unresolved is not None

    @pytest.mark.asyncio
    async def test_every_attached_document_is_referenced(self) -> None:
        request = _request("compare them", stream=True)

        messages, _unresolved = await assemble_provider_messages(
            request,
            [],
            [_document(1, "a.pdf"), _document(2, "b.pdf")],
            "compare them",
            True,
            MagicMock(),
            uploaded_files=[],
            analytics=MagicMock(),
            listed_documents=[],
        )

        file_ids = [b["file_id"] for b in messages[-1]["content"] if b.get("type") == "drive_file"]
        assert file_ids == [1, 2]

    @pytest.mark.asyncio
    async def test_a_turn_with_no_words_references_the_documents_alone(self) -> None:
        """Sending a document and typing nothing leaves no text block to carry."""
        request = _request([{"type": "document", "source": {"type": "base64", "data": ""}}], stream=True)

        messages, _unresolved = await assemble_provider_messages(
            request,
            [],
            [_document(3)],
            "",
            True,
            MagicMock(),
            uploaded_files=[],
            analytics=MagicMock(),
            listed_documents=[],
        )

        blocks = messages[-1]["content"]
        assert blocks == [{"type": "drive_file", "file_id": 3}]

    @pytest.mark.asyncio
    async def test_uploaded_files_still_reach_the_model(self) -> None:
        """Retrieval replaces the request's turns, but not the files sent alongside them."""
        request = _request("what powers a cell?", stream=True)
        uploaded_files = [UploadedFile(name="notes.txt", text="mitochondria")]

        messages, _unresolved = await assemble_provider_messages(
            request,
            [],
            [_document(7)],
            "what powers a cell?",
            True,
            MagicMock(),
            uploaded_files=uploaded_files,
            analytics=MagicMock(),
            listed_documents=[],
        )

        assert messages[0]["content"] == "[File: notes.txt]\n\nmitochondria"


class TestWhenRetrievalWillNotRun:
    """Without retrieval there is nothing synthetic to build or resolve."""

    @pytest.mark.asyncio
    async def test_nothing_is_left_for_the_stream_to_resolve(self) -> None:
        request = _request("just chatting", stream=True)

        _messages, unresolved = await assemble_provider_messages(
            request,
            [],
            [_document()],
            "just chatting",
            False,
            MagicMock(),
            uploaded_files=[],
            analytics=MagicMock(),
            listed_documents=[],
        )

        assert unresolved is None

    @pytest.mark.asyncio
    async def test_retrieval_is_not_called(self) -> None:
        request = _request("just chatting")

        with patch(_RESOLVE, new_callable=AsyncMock) as mock_resolve:
            await assemble_provider_messages(
                request,
                [],
                [_document()],
                "just chatting",
                False,
                MagicMock(),
                uploaded_files=[],
                analytics=MagicMock(),
                listed_documents=[],
            )

        mock_resolve.assert_not_awaited()


class TestTheAttachedDocuments:
    """The planner and its agents name a document by its id, so every turn lists them."""

    @pytest.mark.asyncio
    async def test_they_are_listed_by_id_and_name_before_the_requests_turns(self) -> None:
        request = _request("summarise them")
        db_messages = [_stored("user", "hello"), _stored("assistant", "hi"), _stored("user", "summarise them")]

        messages, _unresolved = await assemble_provider_messages(
            request,
            db_messages,
            [],
            "",
            False,
            MagicMock(),
            uploaded_files=[],
            analytics=MagicMock(),
            listed_documents=[_document(1, "a.pdf"), _document(2, "b.pdf")],
        )

        assert [m["content"] for m in messages] == [
            "hello",
            "hi",
            f"{ATTACHED_DOCUMENTS_HEADING}\n- 1: a.pdf\n- 2: b.pdf",
            "summarise them",
        ]

    @pytest.mark.asyncio
    async def test_a_conversation_with_none_lists_nothing(self) -> None:
        messages, _unresolved = await assemble_provider_messages(
            _request("hello"),
            [],
            [],
            "",
            False,
            MagicMock(),
            uploaded_files=[],
            analytics=MagicMock(),
            listed_documents=[],
        )

        assert [m["content"] for m in messages] == ["hello"]
