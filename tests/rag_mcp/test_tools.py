"""Tests for RAG MCP tools."""

import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.rag.types import RagStatus
from app.rag_mcp.tools import (
    get_chunk_stats,
    get_file_metadata,
    list_file_sections,
    list_user_files,
    search_section_by_keyword,
)


class TestListUserFiles:
    """Test list_user_files tool."""

    @pytest.mark.asyncio
    async def test_returns_ready_files_only(self) -> None:
        """Test that only READY and non-deleted files are returned."""
        mock_file = MagicMock()
        mock_file.id = 1
        mock_file.name = "example.pdf"
        mock_file.mime_type = "application/pdf"
        mock_file.size = 1024
        mock_file.modified_time = datetime(2024, 1, 1)
        mock_file.rag_status = RagStatus.READY
        mock_file.is_deleted = False

        with patch("app.rag_mcp.tools.get_async_session") as mock_get_session:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_result = MagicMock()
            mock_scalars = MagicMock()
            mock_scalars.all.return_value = [mock_file]
            mock_result.scalars.return_value = mock_scalars
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            result = await list_user_files(user_id=1)

            assert len(result) == 1
            assert result[0]["id"] == 1
            assert result[0]["name"] == "example.pdf"

    @pytest.mark.asyncio
    async def test_excludes_deleted_files(self) -> None:
        """Test that deleted files are excluded."""
        with patch("app.rag_mcp.tools.get_async_session") as mock_get_session:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_result = MagicMock()
            mock_scalars = MagicMock()
            mock_scalars.all.return_value = []
            mock_result.scalars.return_value = mock_scalars
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            result = await list_user_files(user_id=1)

            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_excludes_non_ready_files(self) -> None:
        """Test that non-READY files are excluded."""
        with patch("app.rag_mcp.tools.get_async_session") as mock_get_session:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_result = MagicMock()
            mock_scalars = MagicMock()
            mock_scalars.all.return_value = []
            mock_result.scalars.return_value = mock_scalars
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            result = await list_user_files(user_id=1)

            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_sqlalchemy_error_raises(self) -> None:
        """Test that SQLAlchemyError is re-raised."""
        with patch("app.rag_mcp.tools.get_async_session") as mock_get_session:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_session.execute = AsyncMock(side_effect=SQLAlchemyError("DB error"))
            mock_get_session.return_value.__aenter__.return_value = mock_session

            with pytest.raises(SQLAlchemyError):
                await list_user_files(user_id=1)


class TestGetFileMetadata:
    """Test get_file_metadata tool."""

    @pytest.mark.asyncio
    async def test_returns_metadata_for_owned_file(self) -> None:
        """Test that file metadata is returned for an owned file."""
        mock_file = MagicMock()
        mock_file.id = 1
        mock_file.name = "example.pdf"
        mock_file.rag_status = RagStatus.READY
        mock_file.size = 1024
        mock_file.modified_time = datetime(2024, 1, 1)

        with patch("app.rag_mcp.tools.get_async_session") as mock_get_session:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_result = MagicMock()
            mock_scalars = MagicMock()
            mock_scalars.first.return_value = mock_file
            mock_result.scalars.return_value = mock_scalars
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            result = await get_file_metadata(user_id=1, file_id=1)

            assert result is not None
            assert result["id"] == 1
            assert result["name"] == "example.pdf"

    @pytest.mark.asyncio
    async def test_returns_none_for_missing_file(self) -> None:
        """Test that None is returned for missing file."""
        with patch("app.rag_mcp.tools.get_async_session") as mock_get_session:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_result = MagicMock()
            mock_scalars = MagicMock()
            mock_scalars.first.return_value = None
            mock_result.scalars.return_value = mock_scalars
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            result = await get_file_metadata(user_id=1, file_id=999)

            assert result is None

    @pytest.mark.asyncio
    async def test_scoped_to_user_id(self) -> None:
        """Test that the query is scoped to user_id."""
        mock_file = MagicMock()
        mock_file.id = 1

        with patch("app.rag_mcp.tools.get_async_session") as mock_get_session:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_result = MagicMock()
            mock_scalars = MagicMock()
            mock_scalars.first.return_value = mock_file
            mock_result.scalars.return_value = mock_scalars
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            await get_file_metadata(user_id=5, file_id=1)

            assert mock_session.execute.called


class TestListFileSections:
    """Test list_file_sections tool."""

    @pytest.mark.asyncio
    async def test_returns_distinct_tuples(self) -> None:
        """Test that distinct section tuples are returned."""
        mock_file = MagicMock()
        mock_file.id = 1
        mock_file.name = "test.pdf"

        with patch("app.rag_mcp.tools.get_async_session") as mock_get_session:
            mock_session = AsyncMock(spec=AsyncSession)

            mock_file_result = MagicMock()
            mock_file_scalars = MagicMock()
            mock_file_scalars.first.return_value = mock_file
            mock_file_result.scalars.return_value = mock_file_scalars

            mock_sections_result = MagicMock()
            mock_sections_result.all.return_value = [
                ("Ch1", "Sec1", None),
            ]

            mock_session.execute = AsyncMock(side_effect=[mock_file_result, mock_sections_result])
            mock_get_session.return_value.__aenter__.return_value = mock_session

            result = await list_file_sections(user_id=1, file_id=1)

            assert len(result) == 1
            assert result[0]["chapter"] == "Ch1"
            assert result[0]["section"] == "Sec1"

    @pytest.mark.asyncio
    async def test_file_not_found_returns_empty(self) -> None:
        """Test that empty list is returned when file not found."""
        with patch("app.rag_mcp.tools.get_async_session") as mock_get_session:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_result = MagicMock()
            mock_scalars = MagicMock()
            mock_scalars.first.return_value = None
            mock_result.scalars.return_value = mock_scalars
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            result = await list_file_sections(user_id=1, file_id=999)

            assert result == []


class TestGetChunkStats:
    """Test get_chunk_stats tool."""

    @pytest.mark.asyncio
    async def test_returns_count_and_avg_tokens(self) -> None:
        """Test that chunk count and average token count are returned."""
        mock_file = MagicMock()
        mock_file.id = 1
        mock_file.name = "test.pdf"

        with patch("app.rag_mcp.tools.get_async_session") as mock_get_session:
            mock_session = AsyncMock(spec=AsyncSession)

            mock_file_result = MagicMock()
            mock_file_scalars = MagicMock()
            mock_file_scalars.first.return_value = mock_file
            mock_file_result.scalars.return_value = mock_file_scalars

            mock_stats_result = MagicMock()
            mock_stats_row = [42, 128.5]
            mock_stats_result.first.return_value = mock_stats_row

            mock_session.execute = AsyncMock(side_effect=[mock_file_result, mock_stats_result])
            mock_get_session.return_value.__aenter__.return_value = mock_session

            result = await get_chunk_stats(user_id=1, file_id=1)

            assert result is not None
            assert result["chunk_count"] == 42
            assert result["avg_token_count"] == 128.5


class TestSearchSectionByKeyword:
    """Test search_section_by_keyword tool."""

    @pytest.mark.asyncio
    async def test_ilike_match_returned(self) -> None:
        """Test that matching sections are returned."""
        mock_file = MagicMock()
        mock_file.id = 1
        mock_file.name = "test.pdf"

        with patch("app.rag_mcp.tools.get_async_session") as mock_get_session:
            mock_session = AsyncMock(spec=AsyncSession)

            mock_file_result = MagicMock()
            mock_file_scalars = MagicMock()
            mock_file_scalars.first.return_value = mock_file
            mock_file_result.scalars.return_value = mock_file_scalars

            mock_search_result = MagicMock()
            mock_search_result.all.return_value = [
                ("Ch1", "Photosynthesis", None),
            ]

            mock_session.execute = AsyncMock(side_effect=[mock_file_result, mock_search_result])
            mock_get_session.return_value.__aenter__.return_value = mock_session

            result = await search_section_by_keyword(user_id=1, file_id=1, keyword="photo")

            assert len(result) == 1
            assert result[0]["section"] == "Photosynthesis"

    @pytest.mark.asyncio
    async def test_no_match_returns_empty_list(self) -> None:
        """Test that empty list is returned when no matches."""
        mock_file = MagicMock()
        mock_file.id = 1
        mock_file.name = "test.pdf"

        with patch("app.rag_mcp.tools.get_async_session") as mock_get_session:
            mock_session = AsyncMock(spec=AsyncSession)

            mock_file_result = MagicMock()
            mock_file_scalars = MagicMock()
            mock_file_scalars.first.return_value = mock_file
            mock_file_result.scalars.return_value = mock_file_scalars

            mock_search_result = MagicMock()
            mock_search_result.all.return_value = []

            mock_session.execute = AsyncMock(side_effect=[mock_file_result, mock_search_result])
            mock_get_session.return_value.__aenter__.return_value = mock_session

            result = await search_section_by_keyword(user_id=1, file_id=1, keyword="nonexistent")

            assert result == []

    @pytest.mark.asyncio
    async def test_empty_keyword_returns_empty(self) -> None:
        """Test that empty list is returned for empty keyword."""
        result = await search_section_by_keyword(user_id=1, file_id=1, keyword="")

        assert result == []
