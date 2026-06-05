"""Tests for RAG context service functions."""

from unittest.mock import MagicMock

from app.rag.context_service import format_chunks_as_context
from app.rag.enums import RagStatus
from app.rag.models import DocumentChunk
from app.rag.store import SimilarityResult
from app.rag.utils import resolve_source_name as _resolve_source_name


def _make_drive_file(
    *,
    id: int = 1,
    user_id: int = 1,
    name: str = "doc.pdf",
    mime_type: str | None = "application/pdf",
    rag_status: RagStatus | None = RagStatus.READY,
    is_deleted: bool = False,
) -> MagicMock:
    df = MagicMock()
    df.id = id
    df.user_id = user_id
    df.name = name
    df.mime_type = mime_type
    df.rag_status = rag_status
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
