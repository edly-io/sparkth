"""Tests for RAG agent integration in chat routes."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.core_plugins.chat.routes.helpers import resolve_drive_file_blocks
from app.core_plugins.chat.schemas import ChatMessage
from app.rag.context_service import RAGContext, RAGContextService
from app.rag.exceptions import DriveFileNotFoundError, RAGNotReadyError, RAGRetrievalError

_PATCH_TARGET = "app.core_plugins.chat.routes.helpers.get_rag_context_service"


class TestResolveBlocksUsesAgent:
    """Test that resolve_drive_file_blocks uses the agent method."""

    @pytest.mark.asyncio
    async def test_calls_get_context_via_agent(self) -> None:
        """Test that resolve_drive_file_blocks calls get_context_via_agent."""
        messages = [
            ChatMessage(
                role="user",
                content=[
                    {"type": "text", "text": "What is in this file?"},
                    {"type": "drive_file", "file_id": 1},
                ],
            )
        ]

        mock_session = AsyncMock()
        mock_rag_service = MagicMock(spec=RAGContextService)
        mock_context = RAGContext(
            file_db_id=1,
            source_name="test.pdf",
            chunks=[],
            formatted_text="[CONTEXT]",
        )
        mock_rag_service.get_context_via_agent = AsyncMock(return_value=mock_context)

        with patch(_PATCH_TARGET, return_value=mock_rag_service):
            await resolve_drive_file_blocks(
                messages=messages,
                session=mock_session,
                user_id=1,
                llm=MagicMock(),
            )

            # Verify get_context_via_agent was called
            mock_rag_service.get_context_via_agent.assert_called_once()
            call_kwargs = mock_rag_service.get_context_via_agent.call_args[1]
            assert call_kwargs["file_db_id"] == 1
            assert "llm" in call_kwargs

    @pytest.mark.asyncio
    async def test_drive_file_not_found_returns_422(self) -> None:
        """Test that DriveFileNotFoundError returns 422."""
        messages = [
            ChatMessage(
                role="user",
                content=[
                    {"type": "text", "text": "Query"},
                    {"type": "drive_file", "file_id": 999},
                ],
            )
        ]

        mock_session = AsyncMock()
        mock_rag_service = MagicMock(spec=RAGContextService)
        mock_rag_service.get_context_via_agent = AsyncMock(side_effect=DriveFileNotFoundError("Not found"))

        with pytest.raises(HTTPException) as exc_info:
            with patch(_PATCH_TARGET, return_value=mock_rag_service):
                await resolve_drive_file_blocks(
                    messages=messages,
                    session=mock_session,
                    user_id=1,
                    llm=MagicMock(),
                )

        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_rag_not_ready_returns_422(self) -> None:
        """Test that RAGNotReadyError returns 422."""
        messages = [
            ChatMessage(
                role="user",
                content=[
                    {"type": "text", "text": "Query"},
                    {"type": "drive_file", "file_id": 1},
                ],
            )
        ]

        mock_session = AsyncMock()
        mock_rag_service = MagicMock(spec=RAGContextService)
        mock_rag_service.get_context_via_agent = AsyncMock(side_effect=RAGNotReadyError(1, "processing"))

        with pytest.raises(HTTPException) as exc_info:
            with patch(_PATCH_TARGET, return_value=mock_rag_service):
                await resolve_drive_file_blocks(
                    messages=messages,
                    session=mock_session,
                    user_id=1,
                    llm=MagicMock(),
                )

        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_retrieval_error_returns_500(self) -> None:
        """Test that RAGRetrievalError returns 500."""
        messages = [
            ChatMessage(
                role="user",
                content=[
                    {"type": "text", "text": "Query"},
                    {"type": "drive_file", "file_id": 1},
                ],
            )
        ]

        mock_session = AsyncMock()
        mock_rag_service = MagicMock(spec=RAGContextService)
        mock_rag_service.get_context_via_agent = AsyncMock(side_effect=RAGRetrievalError("Retrieval failed"))

        with pytest.raises(HTTPException) as exc_info:
            with patch(_PATCH_TARGET, return_value=mock_rag_service):
                await resolve_drive_file_blocks(
                    messages=messages,
                    session=mock_session,
                    user_id=1,
                    llm=MagicMock(),
                )

        assert exc_info.value.status_code == 500
