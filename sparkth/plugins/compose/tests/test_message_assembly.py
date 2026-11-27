"""Tests for building the message list a provider is sent.

Four things get combined: the conversation's stored history, the files uploaded from the computer, the
documents attached to the conversation, and the turns the request carried.
"""

from typing import Any

from sparkth.lib.documents import Document, DocumentStatus
from sparkth.plugins.compose.constants import ATTACHED_DOCUMENTS_HEADING
from sparkth.plugins.compose.models import Message
from sparkth.plugins.compose.routes.utils.message_assembly import assemble_provider_messages
from sparkth.plugins.compose.schemas import ChatCompletionRequest, ChatMessage, UploadedFile


def _request(*contents: str | list[dict[str, Any]]) -> ChatCompletionRequest:
    return ChatCompletionRequest(llm_config_id=1, messages=[ChatMessage(role="user", content=c) for c in contents])


def _stored(role: str, content: str) -> Message:
    return Message(conversation_id=1, role=role, content=content)


def _document(document_id: int, name: str) -> Document:
    return Document(id=document_id, user_id=1, name=name, status=DocumentStatus.READY)


class TestHistoryAndCurrentTurns:
    """Stored history leads, and the request's own turns replace their stored copies."""

    def test_stored_history_precedes_the_current_turn(self) -> None:
        db_messages = [_stored("user", "hello"), _stored("assistant", "hi"), _stored("user", "what about chapter 3?")]

        messages = assemble_provider_messages(_request("what about chapter 3?"), db_messages, [], [])

        assert [m["content"] for m in messages] == ["hello", "hi", "what about chapter 3?"]

    def test_the_current_turns_come_from_the_request_not_the_database(self) -> None:
        """The stored copy of this turn is flattened text; the request still has its content blocks."""
        blocks: list[dict[str, Any]] = [{"type": "text", "text": "summarise this"}]

        messages = assemble_provider_messages(_request(blocks), [_stored("user", "summarise this")], [], [])

        assert messages[-1]["content"] == blocks

    def test_a_conversation_with_no_prior_turns_sends_only_the_request(self) -> None:
        messages = assemble_provider_messages(_request("first message"), [_stored("user", "first message")], [], [])

        assert [m["content"] for m in messages] == ["first message"]

    def test_uploaded_files_come_between_the_history_and_the_current_turn(self) -> None:
        uploaded_files = [UploadedFile(name="a.txt", text="alpha"), UploadedFile(name="b.txt", text="beta")]
        db_messages = [_stored("user", "hello"), _stored("assistant", "hi"), _stored("user", "summarise them")]

        messages = assemble_provider_messages(_request("summarise them"), db_messages, uploaded_files, [])

        assert [m["content"] for m in messages] == [
            "hello",
            "hi",
            "[File: a.txt]\n\nalpha",
            "[File: b.txt]\n\nbeta",
            "summarise them",
        ]


class TestTheAttachedDocuments:
    """The planner and its agents name a document by its id, so every turn lists them."""

    def test_they_are_listed_by_id_and_name_before_the_requests_turns(self) -> None:
        db_messages = [_stored("user", "hello"), _stored("assistant", "hi"), _stored("user", "summarise them")]
        documents = [_document(1, "a.pdf"), _document(2, "b.pdf")]

        messages = assemble_provider_messages(_request("summarise them"), db_messages, [], documents)

        assert [m["content"] for m in messages] == [
            "hello",
            "hi",
            f"{ATTACHED_DOCUMENTS_HEADING}\n- 1: a.pdf\n- 2: b.pdf",
            "summarise them",
        ]

    def test_a_conversation_with_none_lists_nothing(self) -> None:
        messages = assemble_provider_messages(_request("hello"), [], [], [])

        assert [m["content"] for m in messages] == ["hello"]
