"""Tests for RAG public data types."""

from sparkth.rag.types import DocumentSection, RetrievedChunk


class TestDocumentSection:
    def test_repr_matches_agent_tool_output_format(self) -> None:
        section = DocumentSection(
            source_name="notes.pdf",
            chapter="Chapter 1",
            section="Introduction",
            subsection=None,
            chunk_count=3,
            position_index=0,
        )

        expected = (
            "source_name='notes.pdf' "
            "chapter='Chapter 1' "
            "section='Introduction' "
            "subsection=None "
            "chunk_count=3 "
            "position_index=0"
        )
        assert repr(section) == expected
        assert str(section) == expected


class TestRetrievedChunk:
    def test_fields(self) -> None:
        rc = RetrievedChunk(
            source_name="notes.pdf",
            chapter="Ch1",
            section="1.1",
            subsection=None,
            content="hello world",
        )
        assert rc.source_name == "notes.pdf"
        assert rc.chapter == "Ch1"
        assert rc.section == "1.1"
        assert rc.subsection is None
        assert rc.content == "hello world"
