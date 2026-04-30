"""Tests for RAG MCP database engine."""

import os

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

# Set DATABASE_URL before importing the module
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from app.rag_mcp.db import _get_async_url, get_async_session


class TestRagMcpDb:
    """Test RAG MCP database module."""

    @pytest.mark.asyncio
    async def test_get_async_session_yields_session(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test get_async_session opens and yields an AsyncSession."""
        monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

        # Reimport to pick up the new environment variable
        import importlib

        import app.rag_mcp.db

        importlib.reload(app.rag_mcp.db)

        async with get_async_session() as session:
            assert isinstance(session, AsyncSession)

    def test_async_url_conversion_postgresql(self) -> None:
        """Test _get_async_url converts postgresql to postgresql+asyncpg."""
        result = _get_async_url("postgresql://a:b@host/db")
        assert result == "postgresql+asyncpg://a:b@host/db"

    def test_async_url_conversion_sqlite(self) -> None:
        """Test _get_async_url converts sqlite to sqlite+aiosqlite."""
        result = _get_async_url("sqlite:///./test.db")
        assert result == "sqlite+aiosqlite:///./test.db"
