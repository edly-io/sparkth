"""Tests for RAG integration in chat schemas and route helpers."""

import base64
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.core_plugins.chat.routes import _extract_query_text, _resolve_drive_file_blocks
from app.core_plugins.chat.schemas import ChatMessage
from app.rag.context_service import RAGContext, RAGContextService
from app.rag.exceptions import DriveFileNotFoundError, RAGNotReadyError, RAGRetrievalError


def _user_msg(content: str | list[Any]) -> ChatMessage:
    return ChatMessage(role="user", content=content)


def _assistant_msg(text: str) -> ChatMessage:
    return ChatMessage(role="assistant", content=text)


def _drive_block(file_id: int) -> dict[str, Any]:
    return {"type": "drive_file", "file_id": file_id}


def _text_block(text: str) -> dict[str, Any]:
    return {"type": "text", "text": text}


def _make_rag_service(
    *,
    context: RAGContext | None = None,
    raises: Exception | None = None,
) -> RAGContextService:
    mock_service = MagicMock(spec=RAGContextService)
    if raises:
        mock_service.get_context_for_drive_file = AsyncMock(side_effect=raises)
    else:
        ctx = context or RAGContext(
            file_db_id=1,
            source_name="doc.pdf",
            chunks=[],
            formatted_text="[DOCUMENT CONTEXT: doc.pdf]\nExcerpts here.",
        )
        mock_service.get_context_for_drive_file = AsyncMock(return_value=ctx)
    return mock_service


class TestSchemaValidation:
    def test_valid_drive_file_block_accepted(self) -> None:
        msg = ChatMessage(
            role="user",
            content=[_drive_block(42), _text_block("Generate a course")],
        )
        assert msg.content[0]["type"] == "drive_file"  # type: ignore[index]

    def test_drive_file_block_missing_file_id_rejected(self) -> None:
        with pytest.raises(ValueError, match="file_id"):
            ChatMessage(role="user", content=[{"type": "drive_file"}])

    def test_drive_file_block_zero_file_id_rejected(self) -> None:
        with pytest.raises(ValueError, match="file_id"):
            ChatMessage(role="user", content=[{"type": "drive_file", "file_id": 0}])

    def test_drive_file_block_negative_file_id_rejected(self) -> None:
        with pytest.raises(ValueError, match="file_id"):
            ChatMessage(role="user", content=[{"type": "drive_file", "file_id": -1}])

    def test_drive_file_block_string_file_id_rejected(self) -> None:
        with pytest.raises(ValueError, match="file_id"):
            ChatMessage(role="user", content=[{"type": "drive_file", "file_id": "abc"}])

    def test_base64_block_still_accepted(self) -> None:
        data = base64.b64encode(b"hello").decode()
        msg = ChatMessage(
            role="user",
            content=[{"type": "document", "source": {"type": "base64", "data": data}}],
        )
        assert msg.content[0]["type"] == "document"  # type: ignore[index]


class TestExtractQueryText:
    def test_plain_string_message(self) -> None:
        messages = [_user_msg("Create a course on photosynthesis")]
        assert _extract_query_text(messages) == "Create a course on photosynthesis"

    def test_list_content_extracts_text_blocks(self) -> None:
        messages = [_user_msg([_drive_block(1), _text_block("Create a course on plants")])]
        assert _extract_query_text(messages) == "Create a course on plants"

    def test_uses_last_user_message(self) -> None:
        messages = [
            _user_msg("First message"),
            _assistant_msg("Response"),
            _user_msg("Second message"),
        ]
        assert _extract_query_text(messages) == "Second message"

    def test_no_user_message_returns_empty(self) -> None:
        messages = [_assistant_msg("Hello")]
        assert _extract_query_text(messages) == ""

    def test_list_with_no_text_blocks_returns_empty(self) -> None:
        messages = [_user_msg([_drive_block(1)])]
        assert _extract_query_text(messages) == ""


class TestResolveDriveFileBlocks:
    @pytest.mark.asyncio
    async def test_no_drive_file_blocks_returns_messages_unchanged(self) -> None:
        messages = [_user_msg("Just text"), _assistant_msg("Response")]
        result = await _resolve_drive_file_blocks(
            messages=messages,
            session=AsyncMock(),
            user_id=1,
            rag_service=_make_rag_service(),
        )
        assert result == messages

    @pytest.mark.asyncio
    async def test_drive_file_block_replaced_with_text_block(self) -> None:
        messages = [_user_msg([_drive_block(42), _text_block("Generate a course")])]
        rag_service = _make_rag_service(
            context=RAGContext(
                file_db_id=42,
                source_name="doc.pdf",
                chunks=[],
                formatted_text="[DOCUMENT CONTEXT: doc.pdf]\nContent here.",
            )
        )

        result = await _resolve_drive_file_blocks(
            messages=messages, session=AsyncMock(), user_id=1, rag_service=rag_service
        )

        assert len(result) == 1
        content = result[0].content
        assert isinstance(content, list)
        types = [b["type"] for b in content if isinstance(b, dict)]
        assert "drive_file" not in types
        assert "text" in types
        text_contents = [b["text"] for b in content if isinstance(b, dict) and b.get("type") == "text"]
        assert any("[DOCUMENT CONTEXT" in t for t in text_contents)

    @pytest.mark.asyncio
    async def test_base64_block_passed_through_unchanged(self) -> None:
        data = base64.b64encode(b"hello").decode()
        base64_block = {"type": "document", "source": {"type": "base64", "data": data}}
        messages = [_user_msg([base64_block])]

        result = await _resolve_drive_file_blocks(
            messages=messages, session=AsyncMock(), user_id=1, rag_service=_make_rag_service()
        )
        content = result[0].content
        assert isinstance(content, list)
        assert content[0] == base64_block

    @pytest.mark.asyncio
    async def test_file_not_found_raises_http_422(self) -> None:
        messages = [_user_msg([_drive_block(999)])]
        rag_service = _make_rag_service(raises=DriveFileNotFoundError("not found"))

        with pytest.raises(HTTPException) as exc_info:
            await _resolve_drive_file_blocks(messages=messages, session=AsyncMock(), user_id=1, rag_service=rag_service)
        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_rag_not_ready_raises_http_422_with_status_in_detail(self) -> None:
        messages = [_user_msg([_drive_block(1)])]
        rag_service = _make_rag_service(raises=RAGNotReadyError(1, "processing"))

        with pytest.raises(HTTPException) as exc_info:
            await _resolve_drive_file_blocks(messages=messages, session=AsyncMock(), user_id=1, rag_service=rag_service)
        assert exc_info.value.status_code == 422
        assert "processing" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_retrieval_error_raises_http_500(self) -> None:
        messages = [_user_msg([_drive_block(1)])]
        rag_service = _make_rag_service(raises=RAGRetrievalError("db down"))

        with pytest.raises(HTTPException) as exc_info:
            await _resolve_drive_file_blocks(messages=messages, session=AsyncMock(), user_id=1, rag_service=rag_service)
        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_string_content_message_passed_through(self) -> None:
        messages = [_user_msg("plain text message")]
        result = await _resolve_drive_file_blocks(
            messages=messages, session=AsyncMock(), user_id=1, rag_service=_make_rag_service()
        )
        assert result[0].content == "plain text message"
