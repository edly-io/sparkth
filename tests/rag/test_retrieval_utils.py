"""Tests for RAG retrieval utils — lookup, validation, chunk formatting, and context typing."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.lib.documents import DocumentStatus
from app.rag.exceptions import DocumentNotFoundError, RAGNotReadyError
from app.rag.models import DocumentChunk
from app.rag.retrieval.utils import _lookup_document, format_chunks_as_context, validate_documents_ready
from app.rag.types import RAGContext


def _make_session() -> AsyncMock:
    session = AsyncMock()
    session.exec = AsyncMock()
    return session


def _make_doc(doc_id: int, user_id: int, status: DocumentStatus, is_deleted: bool = False) -> MagicMock:
    doc = MagicMock()
    doc.id = doc_id
    doc.user_id = user_id
    doc.status = status
    doc.is_deleted = is_deleted
    return doc


def _make_chunk(
    content: str = "Some content",
    chapter: str | None = "Chapter 1",
    section: str | None = "Section 1",
    subsection: str | None = None,
) -> DocumentChunk:
    return DocumentChunk(
        user_id=1,
        source_name="doc.pdf",
        content=content,
        chapter=chapter,
        section=section,
        subsection=subsection,
    )


class TestLookupDocument:
    async def test_returns_ready_document(self) -> None:
        doc = _make_doc(1, 1, DocumentStatus.READY)
        session = _make_session()
        result_mock = MagicMock()
        result_mock.first.return_value = doc
        session.exec.return_value = result_mock

        found = await _lookup_document(session, 1)
        assert found is doc

    async def test_raises_not_found_when_missing(self) -> None:
        session = _make_session()
        result_mock = MagicMock()
        result_mock.first.return_value = None
        session.exec.return_value = result_mock

        with pytest.raises(DocumentNotFoundError):
            await _lookup_document(session, 99)

    async def test_raises_not_ready_when_processing(self) -> None:
        doc = _make_doc(1, 1, DocumentStatus.PROCESSING)
        session = _make_session()
        result_mock = MagicMock()
        result_mock.first.return_value = doc
        session.exec.return_value = result_mock

        with pytest.raises(RAGNotReadyError):
            await _lookup_document(session, 1)

    async def test_raises_not_ready_when_queued(self) -> None:
        doc = _make_doc(1, 1, DocumentStatus.QUEUED)
        session = _make_session()
        result_mock = MagicMock()
        result_mock.first.return_value = doc
        session.exec.return_value = result_mock

        with pytest.raises(RAGNotReadyError):
            await _lookup_document(session, 1)


class TestValidateDocumentsReady:
    async def test_passes_when_all_ready(self) -> None:
        docs = [_make_doc(1, 1, DocumentStatus.READY), _make_doc(2, 1, DocumentStatus.READY)]
        session = _make_session()
        result_mock = MagicMock()
        result_mock.all.return_value = docs
        session.exec.return_value = result_mock

        await validate_documents_ready(session, [1, 2])

    async def test_raises_not_found_for_missing_id(self) -> None:
        session = _make_session()
        result_mock = MagicMock()
        result_mock.all.return_value = []
        session.exec.return_value = result_mock

        with pytest.raises(DocumentNotFoundError):
            await validate_documents_ready(session, [99])

    async def test_raises_not_ready_for_non_ready_doc(self) -> None:
        doc = _make_doc(1, 1, DocumentStatus.PROCESSING)
        session = _make_session()
        result_mock = MagicMock()
        result_mock.all.return_value = [doc]
        session.exec.return_value = result_mock

        with pytest.raises(RAGNotReadyError):
            await validate_documents_ready(session, [1])


class TestFormatChunksAsContext:
    def test_no_results_returns_no_excerpts_message(self) -> None:
        result = format_chunks_as_context("doc.pdf", [])
        assert "[DOCUMENT CONTEXT: doc.pdf]" in result
        assert "No relevant excerpts found" in result

    def test_single_result_formatted(self) -> None:
        result = format_chunks_as_context("bio.pdf", [_make_chunk("Chlorophyll content")])
        assert "[DOCUMENT CONTEXT: bio.pdf]" in result
        assert "Chlorophyll content" in result
        assert "Excerpt 1" in result

    def test_multiple_results_numbered(self) -> None:
        results = [_make_chunk(f"Content {i}") for i in range(3)]
        result = format_chunks_as_context("doc.pdf", results)
        assert "Excerpt 1" in result
        assert "Excerpt 2" in result
        assert "Excerpt 3" in result

    def test_section_label_uses_metadata(self) -> None:
        chunk = _make_chunk(content="Text", chapter="Ch1", section="Sec2", subsection=None)
        result = format_chunks_as_context("doc.pdf", [chunk])
        assert "Ch1 / Sec2" in result

    def test_no_metadata_uses_general(self) -> None:
        chunk = _make_chunk(content="Text", chapter=None, section=None, subsection=None)
        result = format_chunks_as_context("doc.pdf", [chunk])
        assert "General" in result


class TestRAGContextType:
    def test_rag_context_constructs_without_ranked_sections(self) -> None:
        """RAGContext can be constructed with just the required fields."""
        ctx = RAGContext(document_id=1, source_name="doc.pdf", chunks=[], formatted_text="")
        assert ctx.document_id == 1
