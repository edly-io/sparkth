"""Tests for batched chunk storage in ChunkStoreService."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.rag.store import ChunkInput, ChunkStoreService


def _make_chunks(n: int, source: str = "test.pdf") -> list[ChunkInput]:
    """Helper to create test chunks."""
    return [ChunkInput(content=f"chunk {i}", source_name=source, chunk_content_hash=f"hash{i}") for i in range(n)]


def _make_mock_chunk_class(n: int) -> MagicMock:
    """Return a mock DocumentChunk class that assigns sequential IDs."""
    counter = [0]

    def make_chunk(**kwargs: object) -> MagicMock:
        counter[0] += 1
        m = MagicMock()
        m.id = counter[0]
        return m

    mock_cls = MagicMock(side_effect=make_chunk)
    return mock_cls


@pytest.mark.asyncio
async def test_store_chunks_splits_into_batches() -> None:
    """With RAG_STORE_BATCH_SIZE=10 and 25 chunks, session.flush is called 3 times."""
    service = ChunkStoreService()
    chunks = _make_chunks(25)

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.expunge_all = MagicMock()

    with (
        patch("app.rag.store.get_settings") as mock_settings,
        patch("app.rag.store.DocumentChunk", side_effect=_make_mock_chunk_class(25).side_effect),
    ):
        mock_settings.return_value.RAG_STORE_BATCH_SIZE = 10
        rows = await service.store_chunks(mock_session, user_id=1, chunks=chunks)

    # 25 chunks / batch_size 10 → 3 flush calls
    assert mock_session.flush.await_count == 3
    assert mock_session.add.call_count == 25
    assert len(rows) == 25
    # Verify all returned values are integers (DocumentChunk IDs)
    assert all(isinstance(row_id, int) for row_id in rows)


@pytest.mark.asyncio
async def test_store_chunks_single_batch_when_chunks_fit() -> None:
    """When all chunks fit in one batch, session.flush is called exactly once."""
    service = ChunkStoreService()
    chunks = _make_chunks(5)

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.expunge_all = MagicMock()

    with (
        patch("app.rag.store.get_settings") as mock_settings,
        patch("app.rag.store.DocumentChunk", side_effect=_make_mock_chunk_class(5).side_effect),
    ):
        mock_settings.return_value.RAG_STORE_BATCH_SIZE = 32
        rows = await service.store_chunks(mock_session, user_id=1, chunks=chunks)

    assert mock_session.flush.await_count == 1
    assert len(rows) == 5


@pytest.mark.asyncio
async def test_store_chunks_empty_returns_empty() -> None:
    """Calling store_chunks with an empty list returns [] without calling session."""
    service = ChunkStoreService()

    mock_session = AsyncMock()
    mock_session.flush = AsyncMock()

    rows = await service.store_chunks(mock_session, user_id=1, chunks=[])

    assert rows == []
    mock_session.flush.assert_not_awaited()
