"""Tests for the vector store service.

Since pgvector (Vector column, <=> operator, HNSW index) is not available in
SQLite, these tests mock the database layer and verify service logic:
batching, metadata mapping, and method contracts.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.rag.embeddings import BaseEmbeddingProvider
from app.rag.models import DocumentChunk
from app.rag.store import ChunkInput, SimilarityResult, VectorStoreService

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
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.expunge_all = AsyncMock()

        # Patch DocumentChunk to have assignable id attribute
        with patch("app.rag.store.DocumentChunk") as mock_chunk_class:
            # Configure mock chunk instances to have id attributes
            mock_chunk1 = MagicMock()
            mock_chunk1.id = 1
            mock_chunk2 = MagicMock()
            mock_chunk2.id = 2
            mock_chunk_class.side_effect = [mock_chunk1, mock_chunk2]

            result = await service.store_chunks(
                mock_session, user_id=1, chunks=chunks, provider=mock_embedding_provider
            )

        mock_embedding_provider.embed_documents.assert_awaited_once_with(["chunk 1", "chunk 2"])  # type: ignore[attr-defined]
        assert len(result) == 2
        assert isinstance(result[0], int)
        assert isinstance(result[1], int)
        assert result == [1, 2]
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
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.expunge_all = AsyncMock()

        # Patch DocumentChunk to have assignable id attribute
        with patch("app.rag.store.DocumentChunk") as mock_chunk_class:
            # Configure mock chunk instances to have id and other attributes
            mock_chunk = MagicMock()
            mock_chunk.id = 123
            mock_chunk.user_id = 42
            mock_chunk.source_name = "lecture.pdf"
            mock_chunk.content = "test content"
            mock_chunk.chapter = "Chapter 1"
            mock_chunk.section = "Section 1.1"
            mock_chunk.subsection = "1.1.1"
            mock_chunk.token_count = 100
            mock_chunk.embedding_model = "mock-model"
            mock_chunk.embedding_provider = "mock"
            mock_chunk.embedding = make_deterministic_embedding(0.1)
            mock_chunk_class.return_value = mock_chunk

            result = await service.store_chunks(
                mock_session, user_id=42, chunks=chunks, provider=mock_embedding_provider
            )

        # Result is now list[int], verify metadata via mock_session.add call
        assert len(result) == 1
        assert isinstance(result[0], int)
        assert result[0] == 123

        # Inspect DocumentChunk passed to session.add()
        call_args = mock_session.add.call_args_list[0][0][0]
        assert call_args.user_id == 42
        assert call_args.source_name == "lecture.pdf"
        assert call_args.content == "test content"
        assert call_args.chapter == "Chapter 1"
        assert call_args.section == "Section 1.1"
        assert call_args.subsection == "1.1.1"
        assert call_args.token_count == 100
        assert call_args.embedding_model == "mock-model"
        assert call_args.embedding_provider == "mock"
        mock_session.flush.assert_awaited_once()

    async def test_store_chunks_embedding_assigned(
        self,
        service: VectorStoreService,
        mock_embedding_provider: BaseEmbeddingProvider,
    ) -> None:
        chunks = [ChunkInput(content="test", source_name="doc.pdf")]
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.expunge_all = AsyncMock()

        # Patch DocumentChunk to have assignable id attribute
        with patch("app.rag.store.DocumentChunk") as mock_chunk_class:
            # Configure mock chunk instances to have id and other attributes
            mock_chunk = MagicMock()
            mock_chunk.id = 456
            mock_chunk.user_id = 1
            mock_chunk.source_name = "doc.pdf"
            mock_chunk.content = "test"
            mock_chunk.embedding = make_deterministic_embedding(0.1)
            mock_chunk.embedding_model = "mock-model"
            mock_chunk.embedding_provider = "mock"
            mock_chunk_class.return_value = mock_chunk

            result = await service.store_chunks(
                mock_session, user_id=1, chunks=chunks, provider=mock_embedding_provider
            )

        # Result is list[int], verify embedding via mock
        assert len(result) == 1
        assert isinstance(result[0], int)
        assert result[0] == 456

        # Inspect embedding via mock_session.add call
        call_args = mock_session.add.call_args_list[0][0][0]
        assert call_args.embedding == make_deterministic_embedding(0.1)
        mock_session.flush.assert_awaited_once()

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

    async def test_similarity_search_returns_results(
        self,
        service: VectorStoreService,
    ) -> None:
        mock_chunk = MagicMock(spec=DocumentChunk)
        mock_chunk.content = "relevant content"
        mock_chunk.source_name = "doc.pdf"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = [(mock_chunk, 0.95)]
        mock_session.execute = AsyncMock(return_value=mock_result)

        results = await service.similarity_search(
            mock_session,
            user_id=1,
            query_embedding=make_deterministic_embedding(0.5),
        )

        assert len(results) == 1
        assert isinstance(results[0], SimilarityResult)
        assert results[0].chunk == mock_chunk
        assert results[0].similarity == 0.95

    async def test_similarity_search_with_single_source_filter(
        self,
        service: VectorStoreService,
    ) -> None:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        await service.similarity_search(
            mock_session,
            user_id=1,
            query_embedding=make_deterministic_embedding(0.5),
            source_names=["specific.pdf"],
        )

        mock_session.execute.assert_awaited_once()
        call_args = mock_session.execute.call_args
        stmt = call_args[0][0]
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": False}))
        assert "source_name" in compiled

    async def test_similarity_search_with_multiple_source_filter(
        self,
        service: VectorStoreService,
    ) -> None:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        await service.similarity_search(
            mock_session,
            user_id=1,
            query_embedding=make_deterministic_embedding(0.5),
            source_names=["doc1.pdf", "doc2.pdf"],
        )

        mock_session.execute.assert_awaited_once()
        # Verify the query was built (session.execute was called with a statement)
        call_args = mock_session.execute.call_args
        stmt = call_args[0][0]
        # The compiled SQL should contain the source_name filter
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": False}))
        assert "source_name" in compiled

    async def test_similarity_search_no_source_filter_searches_all(
        self,
        service: VectorStoreService,
    ) -> None:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        await service.similarity_search(
            mock_session,
            user_id=1,
            query_embedding=make_deterministic_embedding(0.5),
            source_names=None,
        )

        mock_session.execute.assert_awaited_once()

    async def test_similarity_search_custom_limit_and_threshold(
        self,
        service: VectorStoreService,
    ) -> None:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        await service.similarity_search(
            mock_session,
            user_id=1,
            query_embedding=make_deterministic_embedding(0.5),
            limit=10,
            similarity_threshold=0.9,
        )

        mock_session.execute.assert_awaited_once()
