"""Tests for RAG agent integration in chat routes."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.core_plugins.chat.schemas import ChatMessage
from app.lib.rag import (
    DriveFileNotFoundError,
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
    """Test that _resolve_drive_file_blocks delegates to agentic_retrieve_context."""

    @pytest.mark.asyncio
    async def test_calls_retrieve_context(self) -> None:
        """Test that _resolve_drive_file_blocks calls agentic_retrieve_context with correct args."""
        from app.core_plugins.chat.routes import _resolve_drive_file_blocks

        messages = [
            ChatMessage(
                role="user",
                content=[
                    {"type": "text", "text": "What is in this file?"},
                    {"type": "drive_file", "file_id": 1},
                ],
            )
        ]

        mock_session = MagicMock()
        mock_llm = MagicMock()
        with (
            patch("app.core_plugins.chat.routes._to_document_ids", new_callable=AsyncMock) as mock_to_doc_ids,
            patch("app.core_plugins.chat.routes.agentic_retrieve_context", new_callable=AsyncMock) as mock_retrieve,
        ):
            mock_to_doc_ids.return_value = [1]
            mock_retrieve.return_value = [_make_chunk()]
            await _resolve_drive_file_blocks(
                mock_session,
                messages,
                1,
                "What is in this file?",
                mock_llm,
            )

            mock_retrieve.assert_called_once()

            assert mock_retrieve.call_args.args[0] == 1  # user_id
            assert 1 in mock_retrieve.call_args.args[1]  # document_ids
            assert mock_retrieve.call_args.args[3] is not None  # llm

    @pytest.mark.asyncio
    async def test_drive_file_not_found_returns_422(self) -> None:
        """Test that DriveFileNotFoundError returns 422."""
        from app.core_plugins.chat.routes import _resolve_drive_file_blocks

        messages = [
            ChatMessage(
                role="user",
                content=[
                    {"type": "text", "text": "Query"},
                    {"type": "drive_file", "file_id": 999},
                ],
            )
        ]

        mock_session = MagicMock()
        with (
            patch("app.core_plugins.chat.routes._to_document_ids", new_callable=AsyncMock) as mock_to_doc_ids,
            patch("app.core_plugins.chat.routes.agentic_retrieve_context", new_callable=AsyncMock) as mock_retrieve,
        ):
            mock_to_doc_ids.return_value = [999]
            mock_retrieve.side_effect = DriveFileNotFoundError("Not found")
            with pytest.raises(HTTPException) as exc_info:
                await _resolve_drive_file_blocks(
                    mock_session,
                    messages,
                    1,
                    "Query",
                    MagicMock(),
                )

        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_rag_not_ready_returns_422(self) -> None:
        """Test that RAGNotReadyError returns 422."""
        from app.core_plugins.chat.routes import _resolve_drive_file_blocks

        messages = [
            ChatMessage(
                role="user",
                content=[
                    {"type": "text", "text": "Query"},
                    {"type": "drive_file", "file_id": 1},
                ],
            )
        ]

        mock_session = MagicMock()
        with (
            patch("app.core_plugins.chat.routes._to_document_ids", new_callable=AsyncMock) as mock_to_doc_ids,
            patch("app.core_plugins.chat.routes.agentic_retrieve_context", new_callable=AsyncMock) as mock_retrieve,
        ):
            mock_to_doc_ids.return_value = [1]
            mock_retrieve.side_effect = RAGNotReadyError(1, "processing")
            with pytest.raises(HTTPException) as exc_info:
                await _resolve_drive_file_blocks(
                    mock_session,
                    messages,
                    1,
                    "Query",
                    MagicMock(),
                )

        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_retrieval_error_returns_500(self) -> None:
        """Test that RAGRetrievalError returns 500."""
        from app.core_plugins.chat.routes import _resolve_drive_file_blocks

        messages = [
            ChatMessage(
                role="user",
                content=[
                    {"type": "text", "text": "Query"},
                    {"type": "drive_file", "file_id": 1},
                ],
            )
        ]

        mock_session = MagicMock()
        with (
            patch("app.core_plugins.chat.routes._to_document_ids", new_callable=AsyncMock) as mock_to_doc_ids,
            patch("app.core_plugins.chat.routes.agentic_retrieve_context", new_callable=AsyncMock) as mock_retrieve,
        ):
            mock_to_doc_ids.return_value = [1]
            mock_retrieve.side_effect = RAGRetrievalError("Retrieval failed")
            with pytest.raises(HTTPException) as exc_info:
                await _resolve_drive_file_blocks(
                    mock_session,
                    messages,
                    1,
                    "Query",
                    MagicMock(),
                )

        assert exc_info.value.status_code == 500
