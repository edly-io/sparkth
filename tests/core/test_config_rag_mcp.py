"""Tests for RAG MCP configuration."""

import pytest

from app.core.config import Settings


class TestRAGMCPSettings:
    """Test RAG MCP URL setting."""

    def test_default_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test default RAG_MCP_URL value."""
        # Set all required environment variables
        monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
        monkeypatch.setenv("SECRET_KEY", "test-secret-key")
        monkeypatch.setenv("SLACK_CLIENT_ID", "test-slack-id")
        monkeypatch.setenv("SLACK_CLIENT_SECRET", "test-slack-secret")
        monkeypatch.setenv("SLACK_SIGNING_SECRET", "test-slack-signing")
        monkeypatch.setenv("SLACK_REDIRECT_URI", "http://localhost:7727/oauth")

        settings = Settings()
        assert settings.RAG_MCP_URL == "http://rag-mcp:7728/mcp"

    def test_override_via_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test RAG_MCP_URL can be overridden via environment variable."""
        # Set all required environment variables
        monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
        monkeypatch.setenv("SECRET_KEY", "test-secret-key")
        monkeypatch.setenv("SLACK_CLIENT_ID", "test-slack-id")
        monkeypatch.setenv("SLACK_CLIENT_SECRET", "test-slack-secret")
        monkeypatch.setenv("SLACK_SIGNING_SECRET", "test-slack-signing")
        monkeypatch.setenv("SLACK_REDIRECT_URI", "http://localhost:7727/oauth")
        monkeypatch.setenv("RAG_MCP_URL", "http://localhost:9000/mcp")

        settings = Settings()
        assert settings.RAG_MCP_URL == "http://localhost:9000/mcp"
