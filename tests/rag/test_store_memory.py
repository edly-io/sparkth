"""Tests for memory efficiency in chunk storage batching."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.rag.store import ChunkInput, ChunkStoreService


def _make_chunks(n: int, source: str = "test.pdf") -> list[ChunkInput]:
    """Helper to create test chunks."""
    return [ChunkInput(content=f"chunk {i}", source_name=source, chunk_content_hash=f"hash{i}") for i in range(n)]


class TestStoreMemory:
    """Tests for memory-efficient batch processing in store_chunks."""

    @pytest.mark.asyncio
    async def test_store_chunks_returns_list_of_ints(self) -> None:
        """Verify store_chunks returns list[int] not list[DocumentChunk]."""
        service = ChunkStoreService()
        chunks = _make_chunks(3)

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.expunge_all = AsyncMock()

        # Patch DocumentChunk to have assignable id attribute
        with patch("app.rag.store.DocumentChunk") as mock_chunk_class:
            # Configure mock chunk instances to have id attributes
            mock_chunks = []
            for i in range(3):
                mock_chunk = MagicMock()
                mock_chunk.id = i + 1  # Assign IDs 1, 2, 3
                mock_chunks.append(mock_chunk)
            mock_chunk_class.side_effect = mock_chunks

            result = await service.store_chunks(mock_session, user_id=1, chunks=chunks)

        # Verify result is list of ints
        assert isinstance(result, list)
        assert len(result) == 3
        assert all(isinstance(item, int) for item in result)
        assert result == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_store_chunks_expunges_each_batch(self) -> None:
        """Verify session.expunge is called after each batch flush."""
        service = ChunkStoreService()
        chunks = _make_chunks(25)  # 3 batches with batch_size=10

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.expunge_all = AsyncMock()

        with patch("app.rag.store.get_rag_settings") as mock_settings:
            mock_settings.return_value.RAG_STORE_BATCH_SIZE = 10
            await service.store_chunks(mock_session, user_id=1, chunks=chunks)

        # Should call expunge_all once per batch (3 batches for 25 chunks with batch_size=10)
        assert mock_session.expunge_all.call_count == 3
