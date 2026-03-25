"""Tests for the vector store service.

Since pgvector (Vector column, <=> operator, HNSW index) is not available in
SQLite, these tests mock the database layer and verify service logic:
batching, metadata mapping, and method contracts.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.rag.embeddings import BaseEmbeddingProvider
from app.rag.store import ChunkInput, VectorStoreService

from .conftest import make_deterministic_embedding


class TestChunkInput:
    def test_minimal_chunk_input(self) -> None:
        chunk = ChunkInput(content="hello world", source_name="test.pdf")
        assert chunk.content == "hello world"
        assert chunk.source_name == "test.pdf"
        assert chunk.chapter is None
        assert chunk.section is None
        assert chunk.subsection is None
        assert chunk.token_count is None

    def test_full_chunk_input(self) -> None:
        chunk = ChunkInput(
            content="hello world",
            source_name="test.pdf",
            chapter="Chapter 1",
            section="Section 1.1",
            subsection="1.1.1",
            token_count=42,
        )
        assert chunk.chapter == "Chapter 1"
        assert chunk.section == "Section 1.1"
        assert chunk.subsection == "1.1.1"
        assert chunk.token_count == 42


class TestVectorStoreService:
    @pytest.fixture
    def service(self) -> VectorStoreService:
        return VectorStoreService()

    async def test_store_chunks_empty_list(
        self,
        service: VectorStoreService,
        mock_embedding_provider: BaseEmbeddingProvider,
    ) -> None:
        mock_session = AsyncMock()
        result = await service.store_chunks(mock_session, user_id=1, chunks=[], provider=mock_embedding_provider)
        assert result == []
        mock_embedding_provider.embed_documents.assert_not_awaited()  # type: ignore[attr-defined]

    async def test_store_chunks_calls_embed_documents(
        self,
        service: VectorStoreService,
        mock_embedding_provider: BaseEmbeddingProvider,
    ) -> None:
        chunks = [
            ChunkInput(content="chunk 1", source_name="doc.pdf", chapter="Ch1"),
            ChunkInput(content="chunk 2", source_name="doc.pdf", section="Sec1"),
        ]
        mock_session = AsyncMock()

        result = await service.store_chunks(mock_session, user_id=1, chunks=chunks, provider=mock_embedding_provider)

        mock_embedding_provider.embed_documents.assert_awaited_once_with(["chunk 1", "chunk 2"])  # type: ignore[attr-defined]
        assert len(result) == 2
        # Verify session.add was called for each row
        assert mock_session.add.call_count == 2
        mock_session.flush.assert_awaited_once()

    async def test_store_chunks_metadata_mapping(
        self,
        service: VectorStoreService,
        mock_embedding_provider: BaseEmbeddingProvider,
    ) -> None:
        chunks = [
            ChunkInput(
                content="test content",
                source_name="lecture.pdf",
                chapter="Chapter 1",
                section="Section 1.1",
                subsection="1.1.1",
                token_count=100,
            ),
        ]
        mock_session = AsyncMock()

        result = await service.store_chunks(mock_session, user_id=42, chunks=chunks, provider=mock_embedding_provider)

        row = result[0]
        assert row.user_id == 42
        assert row.source_name == "lecture.pdf"
        assert row.content == "test content"
        assert row.chapter == "Chapter 1"
        assert row.section == "Section 1.1"
        assert row.subsection == "1.1.1"
        assert row.token_count == 100
        assert row.embedding_model == "mock-model"
        assert row.embedding_provider == "mock"

    async def test_store_chunks_embedding_assigned(
        self,
        service: VectorStoreService,
        mock_embedding_provider: BaseEmbeddingProvider,
    ) -> None:
        chunks = [ChunkInput(content="test", source_name="doc.pdf")]
        mock_session = AsyncMock()

        result = await service.store_chunks(mock_session, user_id=1, chunks=chunks, provider=mock_embedding_provider)

        # The mock returns [0.1] * EMBEDDING_DIMS for the first chunk
        assert result[0].embedding == make_deterministic_embedding(0.1)

    async def test_delete_by_source(self, service: VectorStoreService) -> None:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 5
        mock_session.execute = AsyncMock(return_value=mock_result)

        count = await service.delete_by_source(mock_session, user_id=1, source_name="old.pdf")

        assert count == 5
        mock_session.execute.assert_awaited_once()
        mock_session.flush.assert_awaited_once()

    async def test_get_sources(self, service: VectorStoreService) -> None:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = [("doc1.pdf",), ("doc2.pdf",)]
        mock_session.execute = AsyncMock(return_value=mock_result)

        sources = await service.get_sources(mock_session, user_id=1)

        assert sources == ["doc1.pdf", "doc2.pdf"]
        mock_session.execute.assert_awaited_once()

    async def test_similarity_search_returns_empty_on_no_results(
        self,
        service: VectorStoreService,
    ) -> None:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        results = await service.similarity_search(
            mock_session,
            user_id=1,
            query_embedding=make_deterministic_embedding(0.5),
        )

        assert results == []
        mock_session.execute.assert_awaited_once()
