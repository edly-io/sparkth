"""Tests for RAG retrieval utils — chunk formatting."""

from unittest.mock import MagicMock

from app.rag.models import DocumentChunk
from app.rag.retrieval.utils import format_chunks_as_context
from app.rag.types import SimilarityResult


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


class TestRAGContextType:
    def test_rag_context_constructs_without_ranked_sections(self) -> None:
        """RAGContext can be constructed with just the required fields."""
        from app.rag.types import RAGContext

        ctx = RAGContext(file_db_id=1, source_name="doc.pdf", chunks=[], formatted_text="")
        assert ctx.file_db_id == 1
