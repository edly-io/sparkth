"""Tests for metadata filtering in VectorStoreService."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.rag.store import VectorStoreService


class TestSimilaritySearchMetadataFilters:
    """Verify that chapter/section/subsection filters are accepted without error."""

    @pytest.mark.asyncio
    async def test_sections_filter_accepted(self) -> None:
        store = VectorStoreService()
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[])))

        await store.similarity_search(
            session=mock_session,
            user_id=1,
            query_embedding=[0.1] * 384,
            sections=["**2. Purpose**", "**3. Processing**"],
        )
        mock_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_chapters_filter_accepted(self) -> None:
        store = VectorStoreService()
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[])))

        await store.similarity_search(
            session=mock_session,
            user_id=1,
            query_embedding=[0.1] * 384,
            chapters=["Chapter 1"],
        )
        mock_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_subsections_filter_accepted(self) -> None:
        store = VectorStoreService()
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[])))

        await store.similarity_search(
            session=mock_session,
            user_id=1,
            query_embedding=[0.1] * 384,
            subsections=["Sub 1"],
        )
        mock_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_filters_backward_compatible(self) -> None:
        store = VectorStoreService()
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[])))

        await store.similarity_search(
            session=mock_session,
            user_id=1,
            query_embedding=[0.1] * 384,
        )
        mock_session.execute.assert_awaited_once()


class TestGetDistinctSections:
    @pytest.mark.asyncio
    async def test_returns_distinct_section_tuples(self) -> None:
        store = VectorStoreService()
        mock_session = AsyncMock()
        mock_rows = [
            (None, "**1. Definitions**", None),
            (None, "**2. Purpose**", None),
            ("Ch1", "**3. Processing**", "Sub1"),
        ]
        mock_result = MagicMock()
        mock_result.all.return_value = mock_rows
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await store.get_distinct_sections(session=mock_session, user_id=1, source_name="doc.pdf")

        assert len(result) == 3
        assert result[0] == {"chapter": None, "section": "**1. Definitions**", "subsection": None}
        assert result[2] == {"chapter": "Ch1", "section": "**3. Processing**", "subsection": "Sub1"}

    @pytest.mark.asyncio
    async def test_empty_result(self) -> None:
        store = VectorStoreService()
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await store.get_distinct_sections(session=mock_session, user_id=1, source_name="doc.pdf")
        assert result == []
