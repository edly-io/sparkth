"""Shared fixtures for RAG tests."""

import os

# Must be set before any app module is imported so get_settings() and
# async_engine are initialised with test values rather than prod defaults.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("RAG_MCP_URL", "http://localhost:8000")
os.environ.setdefault("LLM_ENCRYPTION_KEY", "QL9oJuLxl0gKCbJpQgkzrdlsZUmvIVR3Cp0gSPcVLvQ=")
os.environ.setdefault("SLACK_CLIENT_ID", "test-slack-client-id")
os.environ.setdefault("SLACK_CLIENT_SECRET", "test-slack-client-secret")
os.environ.setdefault("SLACK_SIGNING_SECRET", "test-slack-signing-secret")
os.environ.setdefault("SLACK_REDIRECT_URI", "http://localhost:7727/api/v1/slack/callback")

# app.models.__init__ imports app.rag.db_models (for Alembic autogenerate), and
# app.rag.db_models imports app.models.base, creating a circular dependency.
# Importing app.models here first puts it in sys.modules before any test file
# triggers app.rag.db_models, breaking the cycle.
from collections.abc import AsyncGenerator, Generator
from typing import Any
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel.ext.asyncio.session import AsyncSession

import app.models  # noqa: F401


@pytest.fixture(autouse=True)
def _allow_all_extensions() -> Generator[None, None, None]:
    """Patch extraction settings so no extension is blocked by default.

    Also seeds the int-typed RAG_* settings used by _extract_pdf so tests
    that don't care about them don't trip over MagicMock defaults.

    Tests that specifically test these settings override them via their
    own inner patch() context managers.
    """
    with patch("app.rag.extraction.get_settings") as mock:
        mock.return_value.RAG_ALLOWED_EXTENSIONS = ""
        mock.return_value.RAG_SCANNED_PDF_MIN_CHARS_PER_PAGE = 100
        mock.return_value.RAG_PDF_EXTRACTION_BATCH_SIZE = 10
        yield


@pytest.fixture(scope="session")
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    """Full in-memory SQLite engine with all SQLModel tables."""
    from sqlmodel import SQLModel

    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await eng.dispose()


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Async session with per-test rollback."""
    async with engine.connect() as conn:
        tx = await conn.begin()
        s: Any = AsyncSession(bind=conn)
        try:
            yield s
        finally:
            await s.close()
            await tx.rollback()


@pytest.fixture(scope="session")
async def rag_engine() -> AsyncGenerator[AsyncEngine, None]:
    """In-memory SQLite engine for RAG tests.

    Only the user table is created; chunk persistence is exercised at the
    service level with mocks, so the full schema is unnecessary here.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Only the user table is needed for FK references in service-level tests
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
