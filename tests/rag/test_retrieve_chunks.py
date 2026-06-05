"""Tests for the multi-file retrieval orchestration (app.rag.context_service.retrieve_chunks)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.lib.rag import agentic_retrieve_context as retrieve_chunks
from app.rag.enums import RagStatus
from app.rag.exceptions import DriveFileNotFoundError, RAGNotReadyError, RAGRetrievalError
from app.rag.models import DocumentChunk
from app.rag.store import SimilarityResult
from app.rag.types import RAGContext, RetrievedChunk


def _ctx(source: str, *contents: str) -> RAGContext:
    chunks = [
        SimilarityResult(
            chunk=DocumentChunk(user_id=1, source_name=source, content=c, chapter="Ch", section=None, subsection=None),
            similarity=1.0,
        )
        for c in contents
    ]
    return RAGContext(file_db_id=0, source_name=source, chunks=chunks, formatted_text="")


class TestRetrieveChunks:
    @pytest.mark.asyncio
    async def test_empty_file_ids_returns_empty(self) -> None:
        result = await retrieve_chunks(user_id=1, file_ids=[], query="q", llm=MagicMock())
        assert result == []

    @pytest.mark.asyncio
    async def test_maps_chunks_to_retrieved_chunks(self) -> None:
        with (
            patch("app.lib.rag._validate_files_ready", new=AsyncMock()),
            patch(
                "app.lib.rag.retrieve_context_from_file",
                new=AsyncMock(side_effect=[_ctx("a.pdf", "alpha"), _ctx("b.pdf", "beta")]),
            ),
        ):
            result = await retrieve_chunks(user_id=1, file_ids=[10, 11], query="q", llm=MagicMock())
        assert result == [
            RetrievedChunk(source_name="a.pdf", chapter="Ch", section=None, subsection=None, content="alpha"),
            RetrievedChunk(source_name="b.pdf", chapter="Ch", section=None, subsection=None, content="beta"),
        ]

    @pytest.mark.asyncio
    async def test_not_found_raises_before_search(self) -> None:
        get_ctx = AsyncMock()
        with (
            patch(
                "app.lib.rag._validate_files_ready",
                new=AsyncMock(side_effect=DriveFileNotFoundError("nope")),
            ),
            patch("app.lib.rag.retrieve_context_from_file", new=get_ctx),
        ):
            with pytest.raises(DriveFileNotFoundError):
                await retrieve_chunks(user_id=1, file_ids=[10], query="q", llm=MagicMock())
        get_ctx.assert_not_awaited()  # nothing searched

    @pytest.mark.asyncio
    async def test_not_ready_raises_before_search(self) -> None:
        get_ctx = AsyncMock()
        with (
            patch(
                "app.lib.rag._validate_files_ready",
                new=AsyncMock(side_effect=RAGNotReadyError(10, str(RagStatus.PROCESSING))),
            ),
            patch("app.lib.rag.retrieve_context_from_file", new=get_ctx),
        ):
            with pytest.raises(RAGNotReadyError):
                await retrieve_chunks(user_id=1, file_ids=[10], query="q", llm=MagicMock())
        get_ctx.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_retrieval_error_propagates(self) -> None:
        with (
            patch("app.lib.rag._validate_files_ready", new=AsyncMock()),
            patch(
                "app.lib.rag.retrieve_context_from_file",
                new=AsyncMock(side_effect=RAGRetrievalError("agent boom")),
            ),
        ):
            with pytest.raises(RAGRetrievalError):
                await retrieve_chunks(user_id=1, file_ids=[10], query="q", llm=MagicMock())
