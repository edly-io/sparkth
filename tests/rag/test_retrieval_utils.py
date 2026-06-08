"""Tests for RAG retrieval utils — lookup, validation, chunk formatting, and source name resolution."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.documents.enums import DocumentStatus
from app.rag.exceptions import DocumentNotFoundError, RAGNotReadyError
from app.rag.models import DocumentChunk
from app.rag.retrieval.utils import _lookup_document, format_chunks_as_context, validate_files_ready
from app.rag.types import SimilarityResult
from app.rag.utils import resolve_source_name as _resolve_source_name


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


def _make_drive_file(
    *,
    id: int = 1,
    user_id: int = 1,
    name: str = "doc.pdf",
    mime_type: str | None = "application/pdf",
    is_deleted: bool = False,
) -> MagicMock:
    df = MagicMock()
    df.id = id
    df.user_id = user_id
    df.name = name
    df.mime_type = mime_type
    df.is_deleted = is_deleted
    return df


def _make_chunk(
    content: str = "Some content",
    chapter: str | None = "Chapter 1",
    section: str | None = "Section 1",
    subsection: str | None = None,
) -> MagicMock:
    chunk = MagicMock(spec=DocumentChunk)
    chunk.content = content
    chunk.chapter = chapter
    chunk.section = section
    chunk.subsection = subsection
    return chunk


def _make_sr(content: str = "Content", sim: float = 0.9) -> SimilarityResult:
    return SimilarityResult(chunk=_make_chunk(content), similarity=sim)


class TestLookupDocument:
    async def test_returns_ready_document(self) -> None:
        doc = _make_doc(1, 1, DocumentStatus.READY)
        session = _make_session()
        result_mock = MagicMock()
        result_mock.first.return_value = doc
        session.exec.return_value = result_mock

        found = await _lookup_document(session, 1, 1)
        assert found is doc

    async def test_raises_not_found_when_missing(self) -> None:
        session = _make_session()
        result_mock = MagicMock()
        result_mock.first.return_value = None
        session.exec.return_value = result_mock

        with pytest.raises(DocumentNotFoundError):
            await _lookup_document(session, 1, 99)

    async def test_raises_not_ready_when_processing(self) -> None:
        doc = _make_doc(1, 1, DocumentStatus.PROCESSING)
        session = _make_session()
        result_mock = MagicMock()
        result_mock.first.return_value = doc
        session.exec.return_value = result_mock

        with pytest.raises(RAGNotReadyError):
            await _lookup_document(session, 1, 1)

    async def test_raises_not_ready_when_queued(self) -> None:
        doc = _make_doc(1, 1, DocumentStatus.QUEUED)
        session = _make_session()
        result_mock = MagicMock()
        result_mock.first.return_value = doc
        session.exec.return_value = result_mock

        with pytest.raises(RAGNotReadyError):
            await _lookup_document(session, 1, 1)


class TestValidateFilesReady:
    async def test_passes_when_all_ready(self) -> None:
        docs = [_make_doc(1, 1, DocumentStatus.READY), _make_doc(2, 1, DocumentStatus.READY)]
        session = _make_session()
        result_mock = MagicMock()
        result_mock.all.return_value = docs
        session.exec.return_value = result_mock

        await validate_files_ready(session, 1, [1, 2])

    async def test_raises_not_found_for_missing_id(self) -> None:
        session = _make_session()
        result_mock = MagicMock()
        result_mock.all.return_value = []
        session.exec.return_value = result_mock

        with pytest.raises(DocumentNotFoundError):
            await validate_files_ready(session, 1, [99])

    async def test_raises_not_ready_for_non_ready_doc(self) -> None:
        doc = _make_doc(1, 1, DocumentStatus.PROCESSING)
        session = _make_session()
        result_mock = MagicMock()
        result_mock.all.return_value = [doc]
        session.exec.return_value = result_mock

        with pytest.raises(RAGNotReadyError):
            await validate_files_ready(session, 1, [1])


class TestFormatChunksAsContext:
    def test_no_results_returns_no_excerpts_message(self) -> None:
        result = format_chunks_as_context("doc.pdf", [])
        assert "[DOCUMENT CONTEXT: doc.pdf]" in result
        assert "No relevant excerpts found" in result

    def test_single_result_formatted(self) -> None:
        result = format_chunks_as_context("bio.pdf", [_make_sr("Chlorophyll content")])
        assert "[DOCUMENT CONTEXT: bio.pdf]" in result
        assert "Chlorophyll content" in result
        assert "Excerpt 1" in result

    def test_multiple_results_numbered(self) -> None:
        results = [_make_sr(f"Content {i}") for i in range(3)]
        result = format_chunks_as_context("doc.pdf", results)
        assert "Excerpt 1" in result
        assert "Excerpt 2" in result
        assert "Excerpt 3" in result

    def test_section_label_uses_metadata(self) -> None:
        chunk = _make_chunk(content="Text", chapter="Ch1", section="Sec2", subsection=None)
        result = format_chunks_as_context("doc.pdf", [SimilarityResult(chunk=chunk, similarity=0.8)])
        assert "Ch1 / Sec2" in result

    def test_no_metadata_uses_general(self) -> None:
        chunk = _make_chunk(content="Text", chapter=None, section=None, subsection=None)
        result = format_chunks_as_context("doc.pdf", [SimilarityResult(chunk=chunk, similarity=0.8)])
        assert "General" in result


class TestResolveSourceName:
    def test_regular_pdf_unchanged(self) -> None:
        df = _make_drive_file(name="course.pdf", mime_type="application/pdf")
        assert _resolve_source_name(df) == "course.pdf"

    def test_google_doc_gets_pdf_suffix(self) -> None:
        df = _make_drive_file(
            name="My Course Outline",
            mime_type="application/vnd.google-apps.document",
        )
        assert _resolve_source_name(df) == "My Course Outline.pdf"

    def test_google_doc_already_has_pdf_suffix(self) -> None:
        df = _make_drive_file(name="doc.pdf", mime_type="application/vnd.google-apps.document")
        assert _resolve_source_name(df) == "doc.pdf"

    def test_none_mime_type_unchanged(self) -> None:
        df = _make_drive_file(name="notes.txt", mime_type=None)
        assert _resolve_source_name(df) == "notes.txt"

    def test_google_drawing_gets_pdf_suffix(self) -> None:
        df = _make_drive_file(
            name="diagram",
            mime_type="application/vnd.google-apps.drawing",
        )
        assert _resolve_source_name(df) == "diagram.pdf"


class TestRAGContextType:
    def test_rag_context_constructs_without_ranked_sections(self) -> None:
        """RAGContext can be constructed with just the required fields."""
        from app.rag.types import RAGContext

        ctx = RAGContext(file_db_id=1, source_name="doc.pdf", chunks=[], formatted_text="")
        assert ctx.file_db_id == 1
