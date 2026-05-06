"""Tests for RAG_ALLOWED_EXTENSIONS settings and its parser."""

import pytest

from app.core.config import Settings, parse_rag_allowed_extensions

_REQUIRED = {
    "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
    "SECRET_KEY": "test-secret-key",
    "SLACK_CLIENT_ID": "test-slack-id",
    "SLACK_CLIENT_SECRET": "test-slack-secret",
    "SLACK_SIGNING_SECRET": "test-slack-signing",
    "SLACK_REDIRECT_URI": "http://localhost:7727/oauth",
    "RAG_MCP_URL": "http://rag-mcp:7728/mcp",
}


def _make_settings(monkeypatch: pytest.MonkeyPatch, **extra: str) -> Settings:
    for k, v in _REQUIRED.items():
        monkeypatch.setenv(k, v)
    for k, v in extra.items():
        monkeypatch.setenv(k, v)
    return Settings()


class TestRAGAllowedExtensionsSettings:
    def test_default_is_empty_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Override any value in .env so we get the default
        settings = _make_settings(monkeypatch, RAG_ALLOWED_EXTENSIONS="")
        assert settings.RAG_ALLOWED_EXTENSIONS == ""

    def test_reads_raw_string_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = _make_settings(monkeypatch, RAG_ALLOWED_EXTENSIONS="pdf,txt,docx")
        assert settings.RAG_ALLOWED_EXTENSIONS == "pdf,txt,docx"


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
