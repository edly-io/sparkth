"""Shared pytest fixtures and test environment for the backend test suite.

This module lives under ``app/`` (rather than in a conftest) so that it travels
with the core package: a plugin extracted into its own repository can register
the same shared fixtures via ``pytest_plugins = ["app.testing"]`` in its own
conftest.

Importing this module sets the generic test environment variables as a side
effect, so it must be imported before any ``app.*`` module that reads settings.
Plugin-specific environment (e.g. ``SLACK_*``) belongs in that plugin's own
conftest, not here.
"""

import os

# Set test environment variables BEFORE importing app modules.
# This must happen before app/core/config.py calls get_settings(), which caches
# the settings. We also need DATABASE_URL set before app/core/db.py creates
# the async_engine at import time.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("LLM_ENCRYPTION_KEY", "QL9oJuLxl0gKCbJpQgkzrdlsZUmvIVR3Cp0gSPcVLvQ=")

from collections.abc import AsyncGenerator, Generator
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.cache import get_cache_service
from app.core.db import async_engine
from app.lib.db import get_async_session
from app.main import app
from app.models.user import User


@pytest.fixture(scope="session", autouse=True)
async def dispose_async_engine() -> AsyncGenerator[None, None]:
    """Close the shared async engine once the whole test session is done.

    The ``:memory:`` test database uses a ``StaticPool``, so a single aiosqlite
    connection is kept open for the entire run. aiosqlite runs each connection in
    a *non-daemon* worker thread, which only exits when the connection is closed.
    Without this final dispose the thread lingers and the interpreter hangs
    joining it at shutdown.
    """
    yield
    await async_engine.dispose()


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async database session that will efficiently rollback all changes for all async
    queries.
    """
    async with async_engine.connect() as conn:
        tx = await conn.begin()

        # Create all tables corresponding to all models
        await conn.run_sync(SQLModel.metadata.create_all)

        session = AsyncSession(bind=conn)

        # Override global async sessions
        async def get_async_session_override() -> AsyncGenerator[AsyncSession, None]:
            yield session

        app.dependency_overrides[get_async_session] = get_async_session_override
        try:
            yield session
        finally:
            app.dependency_overrides.pop(get_async_session, None)

            # Rollback the transaction so data is never actually written to the
            # test database.
            await session.close()
            await tx.rollback()


@pytest.fixture
async def client(session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    """
    Similar to TestClient, but for async requests.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as async_client:
        # Use a context manager to ensure that it gets closed after use
        yield async_client


@pytest.fixture
async def current_user(client: AsyncClient) -> AsyncGenerator[User, None]:
    """
    Create a test user and login with this user in all views.
    """
    transport = cast(ASGITransport, client._transport)
    app_instance = cast(FastAPI, transport.app)
    user = User(
        id=1,
        name="Test User",
        username="testuser",
        email="test@example.com",
        hashed_password="fakehashedpassword",
    )

    async def override_user() -> User:
        return user

    app_instance.dependency_overrides[get_current_user] = override_user
    yield user
    app_instance.dependency_overrides.pop(get_current_user, None)


@pytest.fixture(autouse=True)
def _stub_send_verification_email() -> Generator[Any, None, None]:
    """Stub the verification email sender so tests don't hit SMTP.

    Tests that need to assert on send arguments use their own `with patch(...)`
    inside the test body — the inner patch supersedes this autouse stub.
    """
    with patch("app.api.v1.auth.send_verification_email", new_callable=AsyncMock) as stub:
        yield stub


@pytest.fixture(autouse=True)
def _reset_cache_service() -> Generator[None, None, None]:
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

    get_cache_service.cache_clear()


@pytest.fixture(autouse=True)
def _clear_dependency_overrides() -> Generator[None]:
    """
    Clear all application dependency overrides, just in case some things linger around.
    """
    yield
    app.dependency_overrides.clear()
