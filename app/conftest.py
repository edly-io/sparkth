"""Minimal shared fixtures for co-located tests under app/ (e.g. app/core_plugins/*/tests/)."""

import os
from collections.abc import AsyncGenerator, Generator
from typing import Any

# Set test environment variables BEFORE importing app modules.
# This must happen before app/core/config.py calls get_settings(), which caches
# the settings. We also need DATABASE_URL set before app/core/db.py creates
# the async_engine at import time.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("RAG_MCP_URL", "http://localhost:8000")
os.environ.setdefault("LLM_ENCRYPTION_KEY", "QL9oJuLxl0gKCbJpQgkzrdlsZUmvIVR3Cp0gSPcVLvQ=")
os.environ.setdefault("SLACK_CLIENT_ID", "test-slack-client-id")
os.environ.setdefault("SLACK_CLIENT_SECRET", "test-slack-client-secret")
os.environ.setdefault("SLACK_SIGNING_SECRET", "test-slack-signing-secret")
os.environ.setdefault("SLACK_REDIRECT_URI", "http://localhost:7727/api/v1/slack/callback")

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest.fixture(scope="session")
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    """In-memory async engine for co-located app tests."""
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
        s = AsyncSession(bind=conn)
        try:
            yield s
        finally:
            await s.close()
            await tx.rollback()


@pytest.fixture(scope="session")
def sync_engine() -> Generator[Any, None, None]:
    """In-memory sync engine for routes that use synchronous Session."""
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(eng)
    yield eng
    SQLModel.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture
def sync_session(sync_engine: Any) -> Generator[Session, None, None]:
    """Sync session with rollback for each test."""
    connection = sync_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture(autouse=True)
def reset_cache_service() -> Generator[None, None, None]:
    """Clear the get_cache_service lru_cache after each test.

    CacheService holds a Redis connection bound to the event loop that was
    current when connect() first ran.  With per-test (function-scoped) event
    loops each test gets a new loop, but the cached CacheService still holds a
    connection from the previous (now-closed) loop.  When that stale connection
    tries to disconnect it calls self._writer.close() → loop.call_soon() on the
    closed loop → RuntimeError that is not caught by `except RedisError`.

    Clearing the lru_cache forces a fresh CacheService (self._redis = None) for
    every test so the connection is always made in the current loop.
    """
    yield
    from app.core.cache import get_cache_service

    get_cache_service.cache_clear()


@pytest.fixture(autouse=True)
def stub_send_verification_email() -> Generator[Any, None, None]:
    """Stub the verification email sender so tests don't hit SMTP.

    Tests that need to assert on send arguments use their own `with patch(...)`
    inside the test body — the inner patch supersedes this autouse stub.
    """
    from unittest.mock import AsyncMock, patch

    with patch("app.api.v1.auth.send_verification_email", new_callable=AsyncMock) as stub:
        yield stub
