"""Tests for the document chunk store service.

These tests mock the database layer and verify service logic in isolation:
batching, metadata mapping, and method contracts.
"""

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.rag.store import ChunkInput, ChunkStoreService


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


class TestStoreChunksNoProvider:
    """store_chunks no longer accepts a provider parameter."""

    async def test_store_chunks_signature_has_no_provider(self) -> None:
        """store_chunks must not have a 'provider' parameter."""
        sig = inspect.signature(ChunkStoreService.store_chunks)
        assert "provider" not in sig.parameters

    async def test_store_chunks_empty_list_no_provider(self) -> None:
        """Calling store_chunks with no provider succeeds."""
        service = ChunkStoreService()
        mock_session = AsyncMock()
        result = await service.store_chunks(mock_session, user_id=1, chunks=[])
        assert result == []


class TestChunkStoreService:
    @pytest.fixture
    def service(self) -> ChunkStoreService:
        return ChunkStoreService()

    async def test_store_chunks_empty_list(
        self,
        service: ChunkStoreService,
    ) -> None:
        mock_session = AsyncMock()
        result = await service.store_chunks(mock_session, user_id=1, chunks=[])
        assert result == []

    async def test_store_chunks_flushes_session(
        self,
        service: ChunkStoreService,
    ) -> None:
        chunks = [
            ChunkInput(content="chunk 1", source_name="doc.pdf", chapter="Ch1"),
            ChunkInput(content="chunk 2", source_name="doc.pdf", section="Sec1"),
        ]
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.expunge_all = AsyncMock()

        with patch("app.rag.store.DocumentChunk") as mock_chunk_class:
            mock_chunk1 = MagicMock()
            mock_chunk1.id = 1
            mock_chunk2 = MagicMock()
            mock_chunk2.id = 2
            mock_chunk_class.side_effect = [mock_chunk1, mock_chunk2]

            result = await service.store_chunks(mock_session, user_id=1, chunks=chunks)

        assert len(result) == 2
        assert result == [1, 2]
        assert mock_session.add.call_count == 2
        mock_session.flush.assert_awaited_once()

    async def test_store_chunks_metadata_mapping(
        self,
        service: ChunkStoreService,
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

        with patch("app.rag.store.DocumentChunk") as mock_chunk_class:
            mock_chunk = MagicMock()
            mock_chunk.id = 123
            mock_chunk.user_id = 42
            mock_chunk.source_name = "lecture.pdf"
            mock_chunk.content = "test content"
            mock_chunk.chapter = "Chapter 1"
            mock_chunk.section = "Section 1.1"
            mock_chunk.subsection = "1.1.1"
            mock_chunk.token_count = 100
            mock_chunk_class.return_value = mock_chunk

            result = await service.store_chunks(mock_session, user_id=42, chunks=chunks)

        assert len(result) == 1
        assert isinstance(result[0], int)
        assert result[0] == 123

        call_args = mock_session.add.call_args_list[0][0][0]
        assert call_args.user_id == 42
        assert call_args.source_name == "lecture.pdf"
        assert call_args.content == "test content"
        assert call_args.chapter == "Chapter 1"
        assert call_args.section == "Section 1.1"
        assert call_args.subsection == "1.1.1"
        assert call_args.token_count == 100
        mock_session.flush.assert_awaited_once()

    async def test_delete_by_source(self, service: ChunkStoreService) -> None:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 5
        mock_session.execute = AsyncMock(return_value=mock_result)

        count = await service.delete_by_source(mock_session, user_id=1, source_name="old.pdf")

        assert count == 5
        mock_session.execute.assert_awaited_once()
        mock_session.flush.assert_awaited_once()

    async def test_get_sources(self, service: ChunkStoreService) -> None:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = ["doc1.pdf", "doc2.pdf"]
        mock_session.scalars = AsyncMock(return_value=mock_result)

        sources = await service.get_sources(mock_session, user_id=1)

        assert sources == ["doc1.pdf", "doc2.pdf"]
        mock_session.scalars.assert_awaited_once()


class TestDocumentChunkModel:
    def test_embedding_column_removed(self) -> None:
        """DocumentChunk must no longer have an embedding column."""
        from app.rag.db_models import DocumentChunk

        assert not hasattr(DocumentChunk, "embedding")

    def test_embedding_model_column_removed(self) -> None:
        from app.rag.db_models import DocumentChunk

        assert not hasattr(DocumentChunk, "embedding_model")

    def test_embedding_provider_column_removed(self) -> None:
        from app.rag.db_models import DocumentChunk

        assert not hasattr(DocumentChunk, "embedding_provider")
