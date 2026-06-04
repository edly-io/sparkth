"""Tests for RAG public data types."""

from app.rag.types import RetrievedChunk


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
