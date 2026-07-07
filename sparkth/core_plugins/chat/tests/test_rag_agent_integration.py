"""Tests for RAG agent integration in chat route helpers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from sparkth.core_plugins.chat.routes.utils import resolve_document_blocks
from sparkth.core_plugins.chat.schemas import ChatMessage
from sparkth.lib.rag import (
    DocumentNotFoundError,
    RAGNotReadyError,
    RAGRetrievalError,
    RetrievedChunk,
)

RETRIEVE_CONTEXT_PATH = "sparkth.core_plugins.chat.routes.utils.agentic_retrieve_context"


def _make_chunk(
    content: str = "Some content",
    source_name: str = "test.pdf",
) -> RetrievedChunk:
    return RetrievedChunk(
        source_name=source_name,
        chapter=None,
        section="Section 1",
        subsection=None,
        content=content,
    )


class TestResolveDocumentBlocksUsesAgent:
    """Test that resolve_document_blocks delegates to agentic_retrieve_context."""

    @pytest.mark.asyncio
    async def test_calls_retrieve_context(self) -> None:
        messages = [
            ChatMessage(
                role="user",
                content=[
                    {"type": "text", "text": "What is in this document?"},
                    {"type": "drive_file", "file_id": 1},
                ],
            )
        ]

        with patch(RETRIEVE_CONTEXT_PATH, new_callable=AsyncMock) as mock_retrieve:
            mock_retrieve.return_value = [_make_chunk()]

            await resolve_document_blocks(
                messages=messages,
                llm=MagicMock(),
            )

        mock_retrieve.assert_awaited_once()
        await_args = mock_retrieve.await_args
        assert await_args is not None
        assert isinstance(await_args.args[0], str)
        assert 1 in await_args.args[1]
        assert await_args.args[2] is not None

    @pytest.mark.asyncio
    async def test_document_not_found_returns_422(self) -> None:
        messages = [
            ChatMessage(
                role="user",
                content=[
                    {"type": "text", "text": "Query"},
                    {"type": "drive_file", "file_id": 999},
                ],
            )
        ]

        with patch(RETRIEVE_CONTEXT_PATH, new_callable=AsyncMock) as mock_retrieve:
            mock_retrieve.side_effect = DocumentNotFoundError("Not found")

            with pytest.raises(HTTPException) as exc_info:
                await resolve_document_blocks(
                    messages=messages,
                    llm=MagicMock(),
                )

        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_rag_not_ready_returns_422(self) -> None:
        messages = [
            ChatMessage(
                role="user",
                content=[
                    {"type": "text", "text": "Query"},
                    {"type": "drive_file", "file_id": 1},
                ],
            )
        ]

        with patch(RETRIEVE_CONTEXT_PATH, new_callable=AsyncMock) as mock_retrieve:
            mock_retrieve.side_effect = RAGNotReadyError(1, "processing")

            with pytest.raises(HTTPException) as exc_info:
                await resolve_document_blocks(
                    messages=messages,
                    llm=MagicMock(),
                )

        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_retrieval_error_returns_500(self) -> None:
        messages = [
            ChatMessage(
                role="user",
                content=[
                    {"type": "text", "text": "Query"},
                    {"type": "drive_file", "file_id": 1},
                ],
            )
        ]

        with patch(RETRIEVE_CONTEXT_PATH, new_callable=AsyncMock) as mock_retrieve:
            mock_retrieve.side_effect = RAGRetrievalError("Retrieval failed")

            with pytest.raises(HTTPException) as exc_info:
                await resolve_document_blocks(
                    messages=messages,
                    llm=MagicMock(),
                )

        assert exc_info.value.status_code == 500
