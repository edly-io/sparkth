"""Tests for RAG agent integration in chat route helpers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.core_plugins.chat.routes.helpers import resolve_drive_file_blocks
from app.core_plugins.chat.schemas import ChatMessage
from app.lib.rag import (
    DocumentNotFoundError,
    RAGNotReadyError,
    RAGRetrievalError,
    RetrievedChunk,
)


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


class TestResolveBlocksUsesAgent:
    """Test that resolve_drive_file_blocks delegates to agentic_retrieve_context."""

    @pytest.mark.asyncio
    async def test_calls_retrieve_context(self) -> None:
        messages = [
            ChatMessage(
                role="user",
                content=[
                    {"type": "text", "text": "What is in this file?"},
                    {"type": "drive_file", "file_id": 1},
                ],
            )
        ]

        with (
            patch("app.core_plugins.chat.routes.helpers.to_document_ids", new_callable=AsyncMock) as mock_to_doc_ids,
            patch(
                "app.core_plugins.chat.routes.helpers.agentic_retrieve_context", new_callable=AsyncMock
            ) as mock_retrieve,
        ):
            mock_to_doc_ids.return_value = [1]
            mock_retrieve.return_value = [_make_chunk()]

            await resolve_drive_file_blocks(
                messages=messages,
                session=AsyncMock(),
                user_id=1,
                llm=MagicMock(),
            )

        mock_retrieve.assert_awaited_once()
        await_args = mock_retrieve.await_args
        assert await_args is not None
        assert isinstance(await_args.args[0], str)
        assert 1 in await_args.args[1]
        assert await_args.args[2] == 1
        assert await_args.args[3] is not None

    @pytest.mark.asyncio
    async def test_drive_file_not_found_returns_422(self) -> None:
        messages = [
            ChatMessage(
                role="user",
                content=[
                    {"type": "text", "text": "Query"},
                    {"type": "drive_file", "file_id": 999},
                ],
            )
        ]

        with (
            patch("app.core_plugins.chat.routes.helpers.to_document_ids", new_callable=AsyncMock) as mock_to_doc_ids,
            patch(
                "app.core_plugins.chat.routes.helpers.agentic_retrieve_context", new_callable=AsyncMock
            ) as mock_retrieve,
        ):
            mock_to_doc_ids.return_value = [999]
            mock_retrieve.side_effect = DocumentNotFoundError("Not found")

            with pytest.raises(HTTPException) as exc_info:
                await resolve_drive_file_blocks(
                    messages=messages,
                    session=AsyncMock(),
                    user_id=1,
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

        with (
            patch("app.core_plugins.chat.routes.helpers.to_document_ids", new_callable=AsyncMock) as mock_to_doc_ids,
            patch(
                "app.core_plugins.chat.routes.helpers.agentic_retrieve_context", new_callable=AsyncMock
            ) as mock_retrieve,
        ):
            mock_to_doc_ids.return_value = [1]
            mock_retrieve.side_effect = RAGNotReadyError(1, "processing")

            with pytest.raises(HTTPException) as exc_info:
                await resolve_drive_file_blocks(
                    messages=messages,
                    session=AsyncMock(),
                    user_id=1,
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

        with (
            patch("app.core_plugins.chat.routes.helpers.to_document_ids", new_callable=AsyncMock) as mock_to_doc_ids,
            patch(
                "app.core_plugins.chat.routes.helpers.agentic_retrieve_context", new_callable=AsyncMock
            ) as mock_retrieve,
        ):
            mock_to_doc_ids.return_value = [1]
            mock_retrieve.side_effect = RAGRetrievalError("Retrieval failed")

            with pytest.raises(HTTPException) as exc_info:
                await resolve_drive_file_blocks(
                    messages=messages,
                    session=AsyncMock(),
                    user_id=1,
                    llm=MagicMock(),
                )

        assert exc_info.value.status_code == 500
