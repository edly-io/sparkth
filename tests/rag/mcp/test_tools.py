"""Tests for RAG MCP tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.lib.documents import DocumentStatus
from app.rag.mcp.tools import (
    get_chunk_stats,
    get_document_structure,
    get_file_metadata,
    list_file_sections,
    list_user_files,
    search_section_by_keyword,
)


def _mock_document(
    document_id: int = 1,
    name: str = "example.pdf",
    mime_type: str | None = "application/pdf",
    status: DocumentStatus = DocumentStatus.READY,
) -> MagicMock:
    doc = MagicMock()
    doc.id = document_id
    doc.name = name
    doc.mime_type = mime_type
    doc.status = status
    return doc


class TestListUserFiles:
    """Test list_user_files tool."""

    @pytest.mark.asyncio
    async def test_returns_ready_documents_only(self) -> None:
        with patch("app.rag.mcp.tools.session_scope") as mock_get_session:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_result = MagicMock()
            mock_result.all.return_value = [_mock_document(document_id=10)]
            mock_session.exec = AsyncMock(return_value=mock_result)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            result = await list_user_files(user_id=1)

        assert len(result) == 1
        assert result[0].id == 10
        assert result[0].name == "example.pdf"
        assert result[0].mime_type == "application/pdf"
        assert result[0].rag_status == DocumentStatus.READY

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_ready_documents(self) -> None:
        with patch("app.rag.mcp.tools.session_scope") as mock_get_session:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_result = MagicMock()
            mock_result.all.return_value = []
            mock_session.exec = AsyncMock(return_value=mock_result)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            result = await list_user_files(user_id=1)

        assert result == []

    @pytest.mark.asyncio
    async def test_sqlalchemy_error_raises(self) -> None:
        with patch("app.rag.mcp.tools.session_scope") as mock_get_session:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_session.exec = AsyncMock(side_effect=SQLAlchemyError("DB error"))
            mock_get_session.return_value.__aenter__.return_value = mock_session

            with pytest.raises(SQLAlchemyError):
                await list_user_files(user_id=1)


class TestGetFileMetadata:
    """Test get_file_metadata tool."""

    @pytest.mark.asyncio
    async def test_returns_metadata_for_owned_document(self) -> None:
        with patch("app.rag.mcp.tools.session_scope") as mock_get_session:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_doc_result = MagicMock()
            mock_doc_result.first.return_value = _mock_document(document_id=10)
            mock_session.exec = AsyncMock(return_value=mock_doc_result)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            result = await get_file_metadata(user_id=1, document_id=10)

        assert result is not None
        assert result.id == 10
        assert result.name == "example.pdf"
        assert result.mime_type == "application/pdf"
        assert result.rag_status == DocumentStatus.READY

    @pytest.mark.asyncio
    async def test_returns_none_for_missing_document(self) -> None:
        with patch("app.rag.mcp.tools.session_scope") as mock_get_session:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_result = MagicMock()
            mock_result.first.return_value = None
            mock_session.exec = AsyncMock(return_value=mock_result)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            result = await get_file_metadata(user_id=1, document_id=999)

        assert result is None

    @pytest.mark.asyncio
    async def test_scoped_to_user_id(self) -> None:
        with patch("app.rag.mcp.tools.session_scope") as mock_get_session:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_result = MagicMock()
            mock_result.first.return_value = None
            mock_session.exec = AsyncMock(return_value=mock_result)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            await get_file_metadata(user_id=5, document_id=1)

        assert mock_session.exec.called


class TestListFileSections:
    """Test list_file_sections tool."""

    @pytest.mark.asyncio
    async def test_returns_distinct_tuples(self) -> None:
        with patch("app.rag.mcp.tools.session_scope") as mock_get_session:
            mock_session = AsyncMock(spec=AsyncSession)

            mock_doc_result = MagicMock()
            mock_doc_result.first.return_value = _mock_document(document_id=10, name="test.pdf")

            mock_sections_result = MagicMock()
            mock_sections_result.all.return_value = [("Ch1", "Sec1", None)]

            mock_session.exec = AsyncMock(side_effect=[mock_doc_result, mock_sections_result])
            mock_get_session.return_value.__aenter__.return_value = mock_session

            result = await list_file_sections(user_id=1, document_id=10)

        assert len(result) == 1
        assert result[0].chapter == "Ch1"
        assert result[0].section == "Sec1"

    @pytest.mark.asyncio
    async def test_document_not_found_returns_empty(self) -> None:
        with patch("app.rag.mcp.tools.session_scope") as mock_get_session:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_result = MagicMock()
            mock_result.first.return_value = None
            mock_session.exec = AsyncMock(return_value=mock_result)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            result = await list_file_sections(user_id=1, document_id=999)

        assert result == []


class TestGetChunkStats:
    """Test get_chunk_stats tool."""

    @pytest.mark.asyncio
    async def test_returns_count_and_avg_tokens(self) -> None:
        with patch("app.rag.mcp.tools.session_scope") as mock_get_session:
            mock_session = AsyncMock(spec=AsyncSession)

            mock_doc_result = MagicMock()
            mock_doc_result.first.return_value = _mock_document(document_id=10, name="test.pdf")

            mock_stats_result = MagicMock()
            mock_stats_result.first.return_value = [42, 128.5]

            mock_session.exec = AsyncMock(side_effect=[mock_doc_result, mock_stats_result])
            mock_get_session.return_value.__aenter__.return_value = mock_session

            result = await get_chunk_stats(user_id=1, document_id=10)

        assert result is not None
        assert result.source_name == "test.pdf"
        assert result.chunk_count == 42
        assert result.avg_token_count == 128.5


class TestGetDocumentStructure:
    """Test get_document_structure tool."""

    def _make_session(self, document: MagicMock | None, rows: list[tuple]) -> AsyncMock:  # type: ignore[type-arg]
        mock_session = AsyncMock(spec=AsyncSession)

        mock_doc_result = MagicMock()
        mock_doc_result.first.return_value = document

        mock_structure_result = MagicMock()
        mock_structure_result.all.return_value = rows

        if document is None:
            mock_session.exec = AsyncMock(return_value=mock_doc_result)
        else:
            mock_session.exec = AsyncMock(side_effect=[mock_doc_result, mock_structure_result])

        return mock_session

    @pytest.mark.asyncio
    async def test_position_index_assigned_in_order(self) -> None:
        rows = [
            ("Chapter 1", "Introduction", None, 3),
            ("Chapter 1", "Background", None, 5),
            ("Chapter 2", None, None, 2),
        ]
        with patch("app.rag.mcp.tools.session_scope") as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = self._make_session(
                _mock_document(document_id=10, name="test.pdf"), rows
            )
            result = await get_document_structure(user_id=1, document_id=10)

        assert len(result) == 3
        assert [s.position_index for s in result] == [0, 1, 2]

    @pytest.mark.asyncio
    async def test_chunk_count_and_fields_populated(self) -> None:
        rows = [("Ch1", "Sec1", "Sub1", 7)]
        with patch("app.rag.mcp.tools.session_scope") as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = self._make_session(
                _mock_document(document_id=10, name="test.pdf"), rows
            )
            result = await get_document_structure(user_id=1, document_id=10)

        assert len(result) == 1
        section = result[0]
        assert section.chapter == "Ch1"
        assert section.section == "Sec1"
        assert section.subsection == "Sub1"
        assert section.chunk_count == 7
        assert section.position_index == 0
        assert section.source_name == "test.pdf"

    @pytest.mark.asyncio
    async def test_document_not_found_returns_empty(self) -> None:
        with patch("app.rag.mcp.tools.session_scope") as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = self._make_session(None, [])
            result = await get_document_structure(user_id=1, document_id=999)

        assert result == []

    @pytest.mark.asyncio
    async def test_sqlalchemy_error_raises(self) -> None:
        with patch("app.rag.mcp.tools.session_scope") as mock_get_session:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_session.exec = AsyncMock(side_effect=SQLAlchemyError("DB error"))
            mock_get_session.return_value.__aenter__.return_value = mock_session

            with pytest.raises(SQLAlchemyError):
                await get_document_structure(user_id=1, document_id=1)


class TestSearchSectionByKeyword:
    """Test search_section_by_keyword tool."""

    @pytest.mark.asyncio
    async def test_ilike_match_returned(self) -> None:
        with patch("app.rag.mcp.tools.session_scope") as mock_get_session:
            mock_session = AsyncMock(spec=AsyncSession)

            mock_doc_result = MagicMock()
            mock_doc_result.first.return_value = _mock_document(document_id=10, name="test.pdf")

            mock_search_result = MagicMock()
            mock_search_result.all.return_value = [("Ch1", "Photosynthesis", None)]

            mock_session.exec = AsyncMock(side_effect=[mock_doc_result, mock_search_result])
            mock_get_session.return_value.__aenter__.return_value = mock_session

            result = await search_section_by_keyword(user_id=1, document_id=10, keyword="photo")

        assert len(result) == 1
        assert result[0].section == "Photosynthesis"

    @pytest.mark.asyncio
    async def test_no_match_returns_empty_list(self) -> None:
        with patch("app.rag.mcp.tools.session_scope") as mock_get_session:
            mock_session = AsyncMock(spec=AsyncSession)

            mock_doc_result = MagicMock()
            mock_doc_result.first.return_value = _mock_document(document_id=10, name="test.pdf")

            mock_search_result = MagicMock()
            mock_search_result.all.return_value = []

            mock_session.exec = AsyncMock(side_effect=[mock_doc_result, mock_search_result])
            mock_get_session.return_value.__aenter__.return_value = mock_session

            result = await search_section_by_keyword(user_id=1, document_id=10, keyword="nonexistent")

        assert result == []

    @pytest.mark.asyncio
    async def test_empty_keyword_returns_empty(self) -> None:
        result = await search_section_by_keyword(user_id=1, document_id=1, keyword="")
        assert result == []

    @pytest.mark.asyncio
    async def test_backslash_in_keyword_is_escaped(self) -> None:
        from sqlalchemy.dialects import sqlite as sqlite_dialect

        with patch("app.rag.mcp.tools.session_scope") as mock_get_session:
            mock_session = AsyncMock(spec=AsyncSession)

            mock_doc_result = MagicMock()
            mock_doc_result.first.return_value = _mock_document(document_id=10, name="test.pdf")

            mock_search_result = MagicMock()
            mock_search_result.all.return_value = []

            mock_session.exec = AsyncMock(side_effect=[mock_doc_result, mock_search_result])
            mock_get_session.return_value.__aenter__.return_value = mock_session

            await search_section_by_keyword(user_id=1, document_id=10, keyword=r"foo\bar")

        search_stmt = mock_session.exec.call_args_list[1][0][0]
        compiled = search_stmt.compile(
            dialect=sqlite_dialect.dialect(),
            compile_kwargs={"literal_binds": True},
        )
        assert r"%foo\\bar%" in str(compiled)
