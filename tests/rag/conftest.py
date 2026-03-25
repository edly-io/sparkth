"""Shared fixtures for RAG tests."""

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel.ext.asyncio.session import AsyncSession

from app.rag.embeddings import BaseEmbeddingProvider

EMBEDDING_DIMS = 384


def make_deterministic_embedding(seed: float = 0.1) -> list[float]:
    """Return a deterministic embedding vector for testing."""
    return [seed] * EMBEDDING_DIMS


@pytest.fixture
def mock_embedding_provider() -> BaseEmbeddingProvider:
    """A mock embedding provider that returns deterministic vectors."""
    provider = AsyncMock(spec=BaseEmbeddingProvider)
    provider.dimensions = EMBEDDING_DIMS
    provider.provider_name = "mock"
    provider.model_name = "mock-model"
    provider.embed_documents = AsyncMock(
        side_effect=lambda texts: [make_deterministic_embedding(0.1 + i * 0.01) for i in range(len(texts))]
    )
    provider.embed_query = AsyncMock(return_value=make_deterministic_embedding(0.5))
    return provider


@pytest.fixture(scope="session")
async def rag_engine() -> AsyncGenerator[AsyncEngine, None]:
    """In-memory SQLite engine for RAG tests.

    We exclude the DocumentChunk model (pgvector Vector column won't work
    in SQLite) and test at the service level with mocks instead.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Create only non-pgvector tables for integration tests
    from app.models.base import TimestampedModel  # noqa: F401
    from app.models.user import User  # noqa: F401

    async with engine.begin() as conn:
        # Create just the user table (needed for FK references in tests)
        await conn.run_sync(lambda sync_conn: User.metadata.create_all(sync_conn, tables=[User.__table__]))  # type: ignore[attr-defined]
    yield engine
    await engine.dispose()


@pytest.fixture
async def rag_session(rag_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Async session with rollback for each RAG test."""
    async with rag_engine.connect() as conn:
        tx = await conn.begin()
        session: Any = AsyncSession(bind=conn)
        try:
            yield session
        finally:
            await session.close()
            await tx.rollback()
