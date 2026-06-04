"""Tests for RAG_ALLOWED_EXTENSIONS settings and its parser."""

from app.rag.config import parse_rag_allowed_extensions


class TestParseRagAllowedExtensions:
    def test_empty_string_returns_empty_list(self) -> None:
        assert parse_rag_allowed_extensions("") == []

    def test_whitespace_only_returns_empty_list(self) -> None:
        assert parse_rag_allowed_extensions("   ") == []

    def test_parses_comma_separated_string(self) -> None:
        assert parse_rag_allowed_extensions("pdf,txt,docx") == ["pdf", "txt", "docx"]

    def test_strips_whitespace(self) -> None:
        assert parse_rag_allowed_extensions(" pdf , txt , docx ") == ["pdf", "txt", "docx"]

    def test_lowercases_extensions(self) -> None:
        assert parse_rag_allowed_extensions("PDF,TXT,DOCX") == ["pdf", "txt", "docx"]

    def test_strips_leading_dots(self) -> None:
        assert parse_rag_allowed_extensions(".pdf,.txt") == ["pdf", "txt"]

    def test_deduplicates_entries(self) -> None:
        assert parse_rag_allowed_extensions("pdf,txt,pdf") == ["pdf", "txt"]

    def test_ignores_empty_segments(self) -> None:
        assert parse_rag_allowed_extensions("pdf,,txt,") == ["pdf", "txt"]
