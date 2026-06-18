"""Tests for RAG MCP tools (against a real in-memory DB)."""

from typing import Any
from unittest.mock import AsyncMock, patch

from sqlmodel.ext.asyncio.session import AsyncSession

from app.lib.documents import Document, DocumentStatus
from app.rag.mcp.tools import (
    get_chunk_stats,
    get_document_metadata,
    get_document_structure,
    list_document_sections,
    search_section_by_keyword,
)
from app.rag.models import DocumentChunk, DocumentChunkLink
from app.rag.types import DocumentSection


async def _seed_document(
    session: AsyncSession,
    document_id: int = 10,
    name: str = "test.pdf",
    mime_type: str | None = "application/pdf",
    status: DocumentStatus = DocumentStatus.READY,
) -> None:
    session.add(Document(id=document_id, user_id=1, name=name, mime_type=mime_type, status=status))
    await session.commit()


async def _seed_chunks(session: AsyncSession, document_id: int, chunks: list[dict[str, Any]]) -> None:
    """Seed chunks (each dict has ``id`` plus chunk fields) linked to ``document_id``."""
    for chunk in chunks:
        session.add(DocumentChunk(source_name="test.pdf", content="body", **chunk))
        session.add(DocumentChunkLink(document_id=document_id, chunk_id=chunk["id"]))
    await session.commit()


class TestGetDocumentMetadata:
    async def test_returns_metadata_for_document(self, session: AsyncSession) -> None:
        await _seed_document(session, document_id=10, name="example.pdf")

        result = await get_document_metadata(document_id=10)

        assert result is not None
        assert result.id == 10
        assert result.name == "example.pdf"
        assert result.mime_type == "application/pdf"
        assert result.rag_status == DocumentStatus.READY

    async def test_returns_none_for_missing_document(self, session: AsyncSession) -> None:
        result = await get_document_metadata(document_id=999)

        assert result is None


class TestListDocumentSections:
    async def test_returns_distinct_tuples(self, session: AsyncSession) -> None:
        await _seed_document(session, document_id=10)
        await _seed_chunks(
            session,
            10,
            [
                {"id": 1, "chapter": "Ch1", "section": "Sec1", "subsection": None},
                {"id": 2, "chapter": "Ch1", "section": "Sec1", "subsection": None},  # duplicate section
            ],
        )

        result = await list_document_sections(document_id=10)

        assert len(result) == 1
        assert result[0].chapter == "Ch1"
        assert result[0].section == "Sec1"

    async def test_document_not_found_returns_empty(self, session: AsyncSession) -> None:
        result = await list_document_sections(document_id=999)

        assert result == []


class TestGetChunkStats:
    async def test_returns_count_and_avg_tokens(self, session: AsyncSession) -> None:
        await _seed_document(session, document_id=10)
        await _seed_chunks(
            session,
            10,
            [
                {"id": 1, "token_count": 100},
                {"id": 2, "token_count": 157},
            ],
        )

        result = await get_chunk_stats(document_id=10)

        assert result is not None
        assert result.source_name == "test.pdf"
        assert result.chunk_count == 2
        assert result.avg_token_count == 128.5


class TestGetDocumentStructure:
    """``get_document_structure`` is a thin delegation; verify it forwards the id."""

    async def test_delegates_to_rag_ingested_document_structure(self) -> None:
        expected = [
            DocumentSection(
                source_name="test.pdf",
                chapter="Ch1",
                section="Sec1",
                subsection=None,
                chunk_count=7,
                position_index=0,
            )
        ]
        with patch(
            "app.rag.mcp.tools.get_rag_ingested_document_structure",
            new_callable=AsyncMock,
            return_value=expected,
        ) as mock_get_rag_ingested_structure:
            result = await get_document_structure(document_id=10)

        assert result == expected
        mock_get_rag_ingested_structure.assert_awaited_once_with(10)


class TestSearchSectionByKeyword:
    async def test_ilike_match_returned(self, session: AsyncSession) -> None:
        await _seed_document(session, document_id=10)
        await _seed_chunks(
            session,
            10,
            [
                {"id": 1, "chapter": "Ch1", "section": "Photosynthesis", "subsection": None},
                {"id": 2, "chapter": "Ch2", "section": "Respiration", "subsection": None},
            ],
        )

        result = await search_section_by_keyword(document_id=10, keyword="photo")

        assert len(result) == 1
        assert result[0].section == "Photosynthesis"

    async def test_no_match_returns_empty_list(self, session: AsyncSession) -> None:
        await _seed_document(session, document_id=10)
        await _seed_chunks(session, 10, [{"id": 1, "section": "Photosynthesis"}])

        result = await search_section_by_keyword(document_id=10, keyword="nonexistent")

        assert result == []

    async def test_empty_keyword_returns_empty(self) -> None:
        result = await search_section_by_keyword(document_id=1, keyword="")
        assert result == []

    async def test_backslash_in_keyword_is_treated_literally(self, session: AsyncSession) -> None:
        """A backslash in the keyword matches a literal backslash, not as a LIKE escape."""
        await _seed_document(session, document_id=10)
        await _seed_chunks(
            session,
            10,
            [
                {"id": 1, "section": r"foo\bar"},  # literal backslash
                {"id": 2, "section": "foobar"},  # decoy without backslash
            ],
        )

        result = await search_section_by_keyword(document_id=10, keyword=r"foo\bar")

        assert [r.section for r in result] == [r"foo\bar"]
