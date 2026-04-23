"""Tests for batched chunk storage in VectorStoreService."""

from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.rag.store import ChunkInput, VectorStoreService


def _make_chunks(n: int, source: str = "test.pdf") -> list[ChunkInput]:
    """Helper to create test chunks."""
    return [ChunkInput(content=f"chunk {i}", source_name=source, chunk_content_hash=f"hash{i}") for i in range(n)]


@pytest.mark.asyncio
async def test_store_chunks_splits_into_batches(session: AsyncSession) -> None:
    """With RAG_STORE_BATCH_SIZE=10 and 25 chunks, embed_documents is called 3 times."""
    service = VectorStoreService()
    chunks = _make_chunks(25)

    # Each embed call returns a list of [0.1, 0.2, ...] vectors (384 dims)
    fake_embedding = [0.1] * 384

    async def dynamic_embedding_side_effect(texts: List[str]) -> List[List[float]]:
        return [fake_embedding] * len(texts)

    mock_provider = MagicMock()
    mock_provider.model_name = "test-model"
    mock_provider.provider_name = "test"
    mock_provider.embed_documents = AsyncMock(side_effect=dynamic_embedding_side_effect)

    with patch("app.rag.store.get_settings") as mock_settings:
        mock_settings.return_value.RAG_STORE_BATCH_SIZE = 10
        rows = await service.store_chunks(session, user_id=1, chunks=chunks, provider=mock_provider)

    # 25 chunks / batch_size 10 → 3 calls: [0:10], [10:20], [20:25]
    assert mock_provider.embed_documents.call_count == 3
    call_args_list = mock_provider.embed_documents.call_args_list
    assert len(call_args_list[0][0][0]) == 10  # first batch: 10 texts
    assert len(call_args_list[1][0][0]) == 10  # second batch: 10 texts
    assert len(call_args_list[2][0][0]) == 5  # third batch: 5 texts (remainder)
    assert len(rows) == 25


@pytest.mark.asyncio
async def test_store_chunks_single_batch_when_chunks_fit(session: AsyncSession) -> None:
    """When all chunks fit in one batch, embed_documents is called exactly once."""
    service = VectorStoreService()
    chunks = _make_chunks(5)

    fake_embedding = [0.1] * 384
    mock_provider = MagicMock()
    mock_provider.model_name = "test-model"
    mock_provider.provider_name = "test"
    mock_provider.embed_documents = AsyncMock(return_value=[fake_embedding] * 5)

    with patch("app.rag.store.get_settings") as mock_settings:
        mock_settings.return_value.RAG_STORE_BATCH_SIZE = 32
        rows = await service.store_chunks(session, user_id=1, chunks=chunks, provider=mock_provider)

    assert mock_provider.embed_documents.call_count == 1
    assert len(rows) == 5


@pytest.mark.asyncio
async def test_store_chunks_empty_returns_empty(session: AsyncSession) -> None:
    """Calling store_chunks with an empty list returns [] without calling provider."""
    service = VectorStoreService()
    mock_provider = MagicMock()

    rows = await service.store_chunks(session, user_id=1, chunks=[], provider=mock_provider)

    assert rows == []
    mock_provider.embed_documents.assert_not_called()
