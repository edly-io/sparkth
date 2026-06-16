"""Unit tests for RAG chunk formatting utilities."""

from app.lib.rag import RetrievedChunk, format_document_chunks_as_llm_context, group_retrieved_chunks_by_document


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
        result = format_document_chunks_as_llm_context("notes.pdf", [_chunk(content="hello")])
        assert "[DOCUMENT CONTEXT: notes.pdf]" in result

    def test_excerpt_label_uses_section_hierarchy(self) -> None:
        chunk = _chunk(chapter="Ch1", section="S2", subsection="Sub3", content="body")
        result = format_document_chunks_as_llm_context("doc.pdf", [chunk])
        assert "Ch1 / S2 / Sub3" in result

    def test_excerpt_label_falls_back_to_general_when_no_section_data(self) -> None:
        result = format_document_chunks_as_llm_context("doc.pdf", [_chunk(content="body")])
        assert "General" in result

    def test_partial_section_fields_joined(self) -> None:
        chunk = _chunk(chapter="Ch1", section=None, subsection=None, content="body")
        result = format_document_chunks_as_llm_context("doc.pdf", [chunk])
        assert "Ch1" in result
        assert "None" not in result

    def test_multiple_chunks_numbered_sequentially(self) -> None:
        chunks = [_chunk(content="first"), _chunk(content="second")]
        result = format_document_chunks_as_llm_context("doc.pdf", chunks)
        assert "--- Excerpt 1" in result
        assert "--- Excerpt 2" in result

    def test_chunk_content_present_in_output(self) -> None:
        result = format_document_chunks_as_llm_context("doc.pdf", [_chunk(content="unique content xyz")])
        assert "unique content xyz" in result

    def test_empty_chunks_returns_header_only(self) -> None:
        result = format_document_chunks_as_llm_context("doc.pdf", [])
        assert "[DOCUMENT CONTEXT: doc.pdf]" in result
        assert "--- Excerpt" not in result


class TestGroupRetrievedChunksByDocument:
    def test_groups_chunks_by_source_name(self) -> None:
        chunks = [
            _chunk(source_name="a.pdf", content="1"),
            _chunk(source_name="b.pdf", content="2"),
            _chunk(source_name="a.pdf", content="3"),
        ]
        result = group_retrieved_chunks_by_document(chunks)
        assert set(result.keys()) == {"a.pdf", "b.pdf"}
        assert len(result["a.pdf"]) == 2
        assert len(result["b.pdf"]) == 1

    def test_preserves_insertion_order(self) -> None:
        chunks = [
            _chunk(source_name="z.pdf"),
            _chunk(source_name="a.pdf"),
            _chunk(source_name="m.pdf"),
        ]
        result = group_retrieved_chunks_by_document(chunks)
        assert list(result.keys()) == ["z.pdf", "a.pdf", "m.pdf"]

    def test_empty_input_returns_empty_dict(self) -> None:
        assert group_retrieved_chunks_by_document([]) == {}

    def test_single_source_all_chunks_grouped(self) -> None:
        chunks = [_chunk(source_name="x.pdf", content=str(i)) for i in range(5)]
        result = group_retrieved_chunks_by_document(chunks)
        assert list(result.keys()) == ["x.pdf"]
        assert len(result["x.pdf"]) == 5
