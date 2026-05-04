"""Tests for section ranking in RAGContextService."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.rag.constants import DEFAULT_TOP_SECTIONS
from app.rag.context_service import (
    RAGContext,
    RAGContextService,
    _cosine_similarity,
)
from app.rag.types import RagStatus


def _make_drive_file(
    *,
    id: int = 1,
    user_id: int = 1,
    name: str = "doc.pdf",
    mime_type: str | None = "application/pdf",
    rag_status: RagStatus | None = None,
    is_deleted: bool = False,
) -> MagicMock:
    df = MagicMock()
    df.id = id
    df.user_id = user_id
    df.name = name
    df.mime_type = mime_type
    df.rag_status = rag_status or RagStatus.READY
    df.is_deleted = is_deleted
    return df


class TestCosineSimilarity:
    def test_identical_vectors(self) -> None:
        assert _cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)

    def test_orthogonal_vectors(self) -> None:
        assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_zero_vector_returns_zero(self) -> None:
        assert _cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0

    def test_similar_vectors(self) -> None:
        sim = _cosine_similarity([1.0, 1.0], [1.0, 0.0])
        assert 0.5 < sim < 1.0


class TestSectionRanking:
    @pytest.mark.asyncio
    async def test_rank_sections_orders_by_similarity(self) -> None:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = _make_drive_file()
        mock_session.execute = AsyncMock(return_value=mock_result)

        sections = [
            {"chapter": None, "section": "**1. Definitions**", "subsection": None},
            {"chapter": None, "section": "**2. Data Privacy**", "subsection": None},
            {"chapter": None, "section": "**3. AI Development**", "subsection": None},
        ]
        mock_store = AsyncMock()
        mock_store.get_distinct_sections = AsyncMock(return_value=sections)
        mock_store.similarity_search = AsyncMock(return_value=[])

        mock_embedding = AsyncMock()
        mock_embedding.embed_query = AsyncMock(return_value=[1.0, 0.0])
        # Section 2 ([0.9, 0.1]) is most similar to query [1, 0]
        mock_embedding.embed_documents = AsyncMock(return_value=[[0.1, 0.9], [0.9, 0.1], [0.5, 0.5]])

        service = RAGContextService(vector_store=mock_store, embedding_provider=mock_embedding)
        result = await service.get_context_for_drive_file(
            session=mock_session, user_id=1, file_db_id=1, query="data privacy"
        )

        assert isinstance(result, RAGContext)
        assert result.ranked_sections is not None
        assert len(result.ranked_sections) == 3
        assert result.ranked_sections[0]["section"] == "**2. Data Privacy**"

    @pytest.mark.asyncio
    async def test_no_sections_skips_ranking(self) -> None:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = _make_drive_file()
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_store = AsyncMock()
        mock_store.get_distinct_sections = AsyncMock(return_value=[])
        mock_store.similarity_search = AsyncMock(return_value=[])

        mock_embedding = AsyncMock()
        mock_embedding.embed_query = AsyncMock(return_value=[0.1] * 384)

        service = RAGContextService(vector_store=mock_store, embedding_provider=mock_embedding)
        result = await service.get_context_for_drive_file(session=mock_session, user_id=1, file_db_id=1, query="test")

        call_kwargs = mock_store.similarity_search.call_args.kwargs
        assert call_kwargs.get("sections") is None
        assert result.ranked_sections == []

    @pytest.mark.asyncio
    async def test_section_filters_passed_to_similarity_search(self) -> None:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = _make_drive_file()
        mock_session.execute = AsyncMock(return_value=mock_result)

        sections = [{"chapter": None, "section": f"Section {i}", "subsection": None} for i in range(12)]
        mock_store = AsyncMock()
        mock_store.get_distinct_sections = AsyncMock(return_value=sections)
        mock_store.similarity_search = AsyncMock(return_value=[])

        mock_embedding = AsyncMock()
        mock_embedding.embed_query = AsyncMock(return_value=[1.0, 0.0])
        embeddings = [[0.9 - i * 0.05, 0.1 + i * 0.05] for i in range(12)]
        mock_embedding.embed_documents = AsyncMock(return_value=embeddings)

        service = RAGContextService(vector_store=mock_store, embedding_provider=mock_embedding)
        await service.get_context_for_drive_file(session=mock_session, user_id=1, file_db_id=1, query="test")

        call_kwargs = mock_store.similarity_search.call_args.kwargs
        assert call_kwargs.get("sections") is not None
        assert len(call_kwargs["sections"]) <= DEFAULT_TOP_SECTIONS

    @pytest.mark.asyncio
    async def test_ranked_sections_in_rag_context(self) -> None:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = _make_drive_file()
        mock_session.execute = AsyncMock(return_value=mock_result)

        sections = [{"chapter": None, "section": "Sec1", "subsection": None}]
        mock_store = AsyncMock()
        mock_store.get_distinct_sections = AsyncMock(return_value=sections)
        mock_store.similarity_search = AsyncMock(return_value=[])

        mock_embedding = AsyncMock()
        mock_embedding.embed_query = AsyncMock(return_value=[0.1] * 384)
        mock_embedding.embed_documents = AsyncMock(return_value=[[0.1] * 384])

        service = RAGContextService(vector_store=mock_store, embedding_provider=mock_embedding)
        result = await service.get_context_for_drive_file(session=mock_session, user_id=1, file_db_id=1, query="test")

        assert result.ranked_sections is not None
        assert len(result.ranked_sections) == 1
        assert result.ranked_sections[0]["section"] == "Sec1"
