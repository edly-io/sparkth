"""Tests for RAG utility functions (against a real in-memory DB)."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.documents import Document
from sparkth.rag.models import DocumentChunk, DocumentChunkLink
from sparkth.rag.utils import get_rag_ingested_document_structure

# (chapter, section, subsection, [chunk ids]) — chunk ids drive the section ordering
# (sections are ordered by the minimum chunk id within each group).
Group = tuple[str | None, str | None, str | None, list[int]]


async def _seed(session: AsyncSession, document_id: int, name: str, groups: list[Group]) -> None:
    session.add(Document(id=document_id, user_id=1, name=name))
    for chapter, section, subsection, chunk_ids in groups:
        for chunk_id in chunk_ids:
            session.add(
                DocumentChunk(
                    id=chunk_id,
                    source_name=name,
                    content="body",
                    chapter=chapter,
                    section=section,
                    subsection=subsection,
                )
            )
            session.add(DocumentChunkLink(document_id=document_id, chunk_id=chunk_id))
    await session.commit()


class TestGetRagIngestedDocumentStructure:
    async def test_position_index_assigned_in_document_order(self, session: AsyncSession) -> None:
        await _seed(
            session,
            10,
            "test.pdf",
            [
                ("Chapter 1", "Introduction", None, [1, 2, 3]),
                ("Chapter 1", "Background", None, [4, 5, 6, 7, 8]),
                ("Chapter 2", None, None, [9, 10]),
            ],
        )

        result = await get_rag_ingested_document_structure(10)

        assert [section.position_index for section in result] == [0, 1, 2]
        assert [(s.chapter, s.section, s.chunk_count) for s in result] == [
            ("Chapter 1", "Introduction", 3),
            ("Chapter 1", "Background", 5),
            ("Chapter 2", None, 2),
        ]

    async def test_chunk_count_and_section_fields_populated(self, session: AsyncSession) -> None:
        await _seed(session, 10, "test.pdf", [("Ch1", "Sec1", "Sub1", [1, 2, 3, 4, 5, 6, 7])])

        result = await get_rag_ingested_document_structure(10)

        assert len(result) == 1
        section = result[0]
        assert section.source_name == "test.pdf"
        assert section.chapter == "Ch1"
        assert section.section == "Sec1"
        assert section.subsection == "Sub1"
        assert section.chunk_count == 7
        assert section.position_index == 0

    async def test_document_not_found_returns_empty(self, session: AsyncSession) -> None:
        result = await get_rag_ingested_document_structure(999)

        assert result == []

    async def test_sqlalchemy_error_raises(self) -> None:
        with patch(
            "sparkth.rag.utils._fetch_document",
            new=AsyncMock(side_effect=SQLAlchemyError("DB error")),
        ):
            with pytest.raises(SQLAlchemyError):
                await get_rag_ingested_document_structure(1)
