"""Unit tests for RAG chunk formatting utilities."""

from app.lib.rag import RetrievedChunk, format_document_chunks_as_llm_context


def _chunk(
    source_name: str = "doc.pdf",
    chapter: str | None = None,
    section: str | None = None,
    subsection: str | None = None,
    content: str = "content",
) -> RetrievedChunk:
    return RetrievedChunk(
        source_name=source_name,
        chapter=chapter,
        section=section,
        subsection=subsection,
        content=content,
    )


class TestFormatDocumentChunksAsLlmContext:
    def test_contains_document_context_header(self) -> None:
        result = format_document_chunks_as_llm_context([_chunk(source_name="notes.pdf", content="hello")])
        assert "[DOCUMENT CONTEXT: notes.pdf]" in result

    def test_excerpt_label_uses_section_hierarchy(self) -> None:
        chunk = _chunk(chapter="Ch1", section="S2", subsection="Sub3", content="body")
        result = format_document_chunks_as_llm_context([chunk])
        assert "Ch1 / S2 / Sub3" in result

    def test_excerpt_label_falls_back_to_general_when_no_section_data(self) -> None:
        result = format_document_chunks_as_llm_context([_chunk(content="body")])
        assert "General" in result

    def test_partial_section_fields_joined(self) -> None:
        chunk = _chunk(chapter="Ch1", section=None, subsection=None, content="body")
        result = format_document_chunks_as_llm_context([chunk])
        assert "Ch1" in result
        assert "None" not in result

    def test_multiple_chunks_numbered_sequentially(self) -> None:
        chunks = [_chunk(content="first"), _chunk(content="second")]
        result = format_document_chunks_as_llm_context(chunks)
        assert "--- Excerpt 1" in result
        assert "--- Excerpt 2" in result

    def test_chunk_content_present_in_output(self) -> None:
        result = format_document_chunks_as_llm_context([_chunk(content="unique content xyz")])
        assert "unique content xyz" in result

    def test_empty_input_returns_empty_string(self) -> None:
        assert format_document_chunks_as_llm_context([]) == ""

    def test_groups_chunks_into_per_document_blocks(self) -> None:
        chunks = [
            _chunk(source_name="a.pdf", content="alpha"),
            _chunk(source_name="b.pdf", content="bravo"),
            _chunk(source_name="a.pdf", content="alpha2"),
        ]
        result = format_document_chunks_as_llm_context(chunks)
        assert "[DOCUMENT CONTEXT: a.pdf]" in result
        assert "[DOCUMENT CONTEXT: b.pdf]" in result
        # Each document's block restarts excerpt numbering, so "Excerpt 1" appears once per document.
        assert result.count("--- Excerpt 1") == 2
        assert "alpha" in result and "alpha2" in result and "bravo" in result

    def test_preserves_first_seen_document_order(self) -> None:
        chunks = [
            _chunk(source_name="z.pdf", content="z"),
            _chunk(source_name="a.pdf", content="a"),
            _chunk(source_name="m.pdf", content="m"),
        ]
        result = format_document_chunks_as_llm_context(chunks)
        assert result.index("z.pdf") < result.index("a.pdf") < result.index("m.pdf")
