"""Tests for RAG document structure lookup."""

from collections.abc import Sequence
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.rag.structure import get_document_structure


def _mock_document(document_id: int, name: str) -> MagicMock:
    document = MagicMock()
    document.id = document_id
    document.name = name
    return document


def _make_session(
    document: MagicMock | None,
    rows: Sequence[tuple[str | None, str | None, str | None, int]],
) -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)

    document_result = MagicMock()
    document_result.first.return_value = document

    structure_result = MagicMock()
    structure_result.all.return_value = rows

    if document is None:
        session.exec = AsyncMock(return_value=document_result)
    else:
        session.exec = AsyncMock(side_effect=[document_result, structure_result])

    return session


class TestGetDocumentStructure:
    @pytest.mark.asyncio
    async def test_position_index_assigned_in_document_order(self) -> None:
        rows = [
            ("Chapter 1", "Introduction", None, 3),
            ("Chapter 1", "Background", None, 5),
            ("Chapter 2", None, None, 2),
        ]
        with patch("app.rag.structure.session_scope") as mock_scope:
            mock_scope.return_value.__aenter__.return_value = _make_session(
                _mock_document(document_id=10, name="test.pdf"), rows
            )

            result = await get_document_structure(1, 10)

        assert [section.position_index for section in result] == [0, 1, 2]

    @pytest.mark.asyncio
    async def test_chunk_count_and_section_fields_populated(self) -> None:
        with patch("app.rag.structure.session_scope") as mock_scope:
            mock_scope.return_value.__aenter__.return_value = _make_session(
                _mock_document(document_id=10, name="test.pdf"),
                [("Ch1", "Sec1", "Sub1", 7)],
            )

            result = await get_document_structure(1, 10)

        assert len(result) == 1
        section = result[0]
        assert section.source_name == "test.pdf"
        assert section.chapter == "Ch1"
        assert section.section == "Sec1"
        assert section.subsection == "Sub1"
        assert section.chunk_count == 7
        assert section.position_index == 0

    @pytest.mark.asyncio
    async def test_document_not_found_returns_empty(self) -> None:
        with patch("app.rag.structure.session_scope") as mock_scope:
            mock_scope.return_value.__aenter__.return_value = _make_session(None, [])

            result = await get_document_structure(1, 999)

        assert result == []

    @pytest.mark.asyncio
    async def test_sqlalchemy_error_raises(self) -> None:
        with patch("app.rag.structure.session_scope") as mock_scope:
            session = AsyncMock(spec=AsyncSession)
            session.exec = AsyncMock(side_effect=SQLAlchemyError("DB error"))
            mock_scope.return_value.__aenter__.return_value = session

            with pytest.raises(SQLAlchemyError):
                await get_document_structure(1, 1)
