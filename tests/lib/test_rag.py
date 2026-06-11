"""Tests for the app.lib.rag public API surface and ingest_document.

Everything here is imported from app.lib.rag only — this suite exercises the
public boundary, never the RAG internals behind it.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.lib.rag as rag_api
import app.rag.utils as rag_utils
from app.lib.rag import (
    DocumentSection,
    ScannedPDFError,
    UnsupportedFileTypeError,
    agentic_retrieve_context,
    ingest_document,
)


class TestRagPublicApi:
    def test_exposes_ingest_document(self) -> None:
        assert callable(rag_api.ingest_document)

    def test_exposes_retrieved_chunk_type(self) -> None:
        rc = rag_api.RetrievedChunk(source_name="x.pdf", chapter=None, section=None, subsection=None, content="c")
        assert rc.source_name == "x.pdf"

    def test_exposes_document_section_type(self) -> None:
        section = DocumentSection(
            source_name="x.pdf",
            chapter="Chapter",
            section=None,
            subsection=None,
            chunk_count=2,
            position_index=0,
        )
        assert section.source_name == "x.pdf"

    def test_exposes_rag_ingested_document_structure_lookup(self) -> None:
        assert callable(rag_api.get_rag_ingested_document_structure)

    def test_exposes_ingestion_exceptions(self) -> None:
        assert issubclass(rag_api.UnsupportedFileTypeError, Exception)
        assert issubclass(rag_api.ScannedPDFError, Exception)


class TestIngestDocument:
    @pytest.mark.asyncio
    async def test_unsupported_type_raises_before_extraction(self) -> None:
        with pytest.raises(UnsupportedFileTypeError):
            await ingest_document("img.png", b"x", 10, 1)

    @pytest.mark.asyncio
    async def test_empty_chunks_returns_zero_counts(self) -> None:
        extraction = MagicMock(markdown="")
        chunker = MagicMock()
        chunker.return_value.chunk.return_value = []
        with (
            patch("app.rag.ingestion.extract_to_markdown", return_value=extraction),
            patch("app.rag.ingestion.DocumentChunker", chunker),
        ):
            result = await ingest_document("a.txt", b"x", 10, 1)
        assert result.new_chunks == 0
        assert result.reused_chunks == 0

    @pytest.mark.asyncio
    async def test_scanned_pdf_propagates(self) -> None:
        with patch("app.rag.ingestion.extract_to_markdown", side_effect=ScannedPDFError("a.pdf")):
            with pytest.raises(ScannedPDFError):
                await ingest_document("a.pdf", b"x", 10, 1)

    @pytest.mark.asyncio
    async def test_happy_path_returns_counts(self) -> None:
        extraction = MagicMock(markdown="# H\ntext")
        chunker = MagicMock()
        chunker.return_value.chunk.return_value = [MagicMock()]
        with (
            patch("app.rag.ingestion.extract_to_markdown", return_value=extraction),
            patch("app.rag.ingestion.DocumentChunker", chunker),
            patch("app.rag.ingestion.session_scope") as mock_scope,
            patch("app.rag.ingestion.store_and_link_chunks", return_value=(1, 0)) as mock_store,
        ):
            mock_session = AsyncMock()
            mock_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await ingest_document("a.txt", b"x", 10, 1)
        assert result.new_chunks == 1
        assert result.reused_chunks == 0
        mock_store.assert_awaited_once()
        mock_session.commit.assert_awaited_once()


class TestRetrieveContextSurface:
    def test_exposes_retrieve_context(self) -> None:
        assert callable(rag_api.agentic_retrieve_context)

    def test_exposes_retrieved_chunk(self) -> None:
        rc = rag_api.RetrievedChunk(source_name="a.pdf", chapter=None, section=None, subsection=None, content="x")
        assert rc.content == "x"

    def test_exposes_retrieval_exceptions(self) -> None:
        assert issubclass(rag_api.DocumentNotFoundError, Exception)
        assert issubclass(rag_api.RAGNotReadyError, Exception)
        assert issubclass(rag_api.RAGRetrievalError, Exception)


class TestRetrieveContext:
    @pytest.mark.asyncio
    async def test_empty_document_ids_returns_empty(self) -> None:
        result = await agentic_retrieve_context("q", [], 1, MagicMock())
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_retrieved_chunks_from_document(self) -> None:
        from app.rag.models import DocumentChunk
        from app.rag.types import RAGContext

        mock_ctx = RAGContext(
            document_id=10,
            source_name="a.pdf",
            chunks=[
                DocumentChunk(
                    user_id=1,
                    source_name="a.pdf",
                    content="hello",
                    chapter="Ch",
                    section=None,
                    subsection=None,
                )
            ],
            formatted_text="",
        )
        with (
            patch("app.rag.retrieval.validate_documents_ready", new=AsyncMock()),
            patch(
                "app.rag.retrieval.get_context_via_agent_with_isolated_session", new=AsyncMock(return_value=mock_ctx)
            ) as mock_fn,
        ):
            result = await agentic_retrieve_context("q", [10], 1, MagicMock())
        assert len(result) == 1
        assert result[0].content == "hello"
        assert result[0].source_name == "a.pdf"
        mock_fn.assert_awaited_once()


class TestRagIngestedDocumentStructureSurface:
    def test_get_rag_ingested_document_structure_is_reexported(self) -> None:
        assert rag_api.get_rag_ingested_document_structure is rag_utils.get_rag_ingested_document_structure
