"""Tests for the app.lib.rag public API surface and ingest_document.

Everything here is imported from app.lib.rag only — this suite exercises the
public boundary, never the RAG internals behind it.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.language_models import BaseChatModel

import app.lib.rag as rag_api
from app.lib.rag import (
    IngestionResult,
    ScannedPDFError,
    UnsupportedFileTypeError,
    ingest_document,
)


class TestRagPublicApi:
    def test_exposes_ingest_document(self) -> None:
        assert callable(rag_api.ingest_document)

    def test_exposes_ingestion_result(self) -> None:
        assert rag_api.IngestionResult(new_chunks=1, reused_chunks=2).new_chunks == 1

    def test_exposes_rag_status(self) -> None:
        assert rag_api.RagStatus.READY is rag_api.RagStatus.READY

    def test_exposes_ingestion_exceptions(self) -> None:
        assert issubclass(rag_api.UnsupportedFileTypeError, Exception)
        assert issubclass(rag_api.ScannedPDFError, Exception)


class TestIngestDocument:
    @pytest.mark.asyncio
    async def test_unsupported_type_raises_before_extraction(self) -> None:
        with pytest.raises(UnsupportedFileTypeError):
            await ingest_document(user_id=1, owner_file_id=10, file_bytes=b"x", filename="img.png")

    @pytest.mark.asyncio
    async def test_empty_chunks_returns_zero_counts(self) -> None:
        extraction = MagicMock(markdown="")
        chunker = MagicMock()
        chunker.return_value.chunk.return_value = []
        with (
            patch("app.lib.rag.extract_to_markdown", return_value=extraction),
            patch("app.lib.rag.DocumentChunker", chunker),
        ):
            result = await ingest_document(user_id=1, owner_file_id=10, file_bytes=b"x", filename="a.txt")
        assert result == IngestionResult(new_chunks=0, reused_chunks=0)

    @pytest.mark.asyncio
    async def test_scanned_pdf_propagates(self) -> None:
        with patch("app.lib.rag.extract_to_markdown", side_effect=ScannedPDFError("a.pdf")):
            with pytest.raises(ScannedPDFError):
                await ingest_document(user_id=1, owner_file_id=10, file_bytes=b"x", filename="a.pdf")

    @pytest.mark.asyncio
    async def test_happy_path_returns_counts(self) -> None:
        extraction = MagicMock(markdown="# H\ntext")
        chunker = MagicMock()
        chunker.return_value.chunk.return_value = [MagicMock()]
        with (
            patch("app.lib.rag.extract_to_markdown", return_value=extraction),
            patch("app.lib.rag.DocumentChunker", chunker),
            patch("app.lib.rag.session_scope") as mock_scope,
            patch("app.lib.rag.store_and_link_chunks", return_value=(1, 0)) as mock_store,
        ):
            mock_session = AsyncMock()
            mock_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await ingest_document(user_id=1, owner_file_id=10, file_bytes=b"x", filename="a.txt")
        assert result == IngestionResult(new_chunks=1, reused_chunks=0)
        mock_store.assert_awaited_once()
        mock_session.commit.assert_awaited_once()


class TestRetrieveContextSurface:
    def test_exposes_retrieve_context(self) -> None:
        assert callable(rag_api.retrieve_context)

    def test_exposes_retrieved_chunk(self) -> None:
        rc = rag_api.RetrievedChunk(source_name="a.pdf", chapter=None, section=None, subsection=None, content="x")
        assert rc.content == "x"

    def test_exposes_retrieval_exceptions(self) -> None:
        assert issubclass(rag_api.DriveFileNotFoundError, Exception)
        assert issubclass(rag_api.RAGNotReadyError, Exception)
        assert issubclass(rag_api.RAGRetrievalError, Exception)


class TestRetrieveContext:
    @pytest.mark.asyncio
    async def test_delegates_to_orchestration(self) -> None:
        chunk = rag_api.RetrievedChunk(source_name="a.pdf", chapter=None, section=None, subsection=None, content="x")
        mock_llm = MagicMock(spec=BaseChatModel)
        with patch("app.lib.rag.retrieve_chunks", new=AsyncMock(return_value=[chunk])) as mock_retrieve:
            result = await rag_api.retrieve_context(user_id=1, file_ids=[10], query="q", llm=mock_llm)
        assert result == [chunk]
        mock_retrieve.assert_awaited_once()
