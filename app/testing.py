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
# the settings on first use.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("LLM_ENCRYPTION_KEY", "QL9oJuLxl0gKCbJpQgkzrdlsZUmvIVR3Cp0gSPcVLvQ=")

from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

import app.core.db as core_db
import app.lib.db as db
from app.api.v1.auth import get_current_user
from app.core.cache import get_cache_service
from app.core.db import dispose_engine, get_engine
from app.main import app
from app.models.user import User


@pytest.fixture(autouse=True)
async def _db_schema(monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[None]:
    """Migrate the in-memory database on first session use, then dispose it.

    The test ``DATABASE_URL`` is an in-memory SQLite database backed by a
    ``StaticPool``: one connection, one database, for the engine's whole lifetime.

    We override the single low-level provider ``app.core.db.open_session`` to create
    the schema on first use. ``session_scope`` resolves ``open_session`` via module
    attribute at call time, so this one override reaches *every* call path — the
    ``session`` fixture, the request path, ``get_async_session``, and direct
    ``session_scope`` calls in background/CLI/MCP code — including modules that did
    ``from app.lib.db import session_scope``. It stays lazy: tests that never open a
    session build no engine and pay nothing.

    Disposing the engine afterwards means the next ``get_engine()`` rebuilds an empty
    database; that disposal *is* the test isolation, not rollback.
    """
    real_open_session = core_db.open_session
    schema_created = False

    @asynccontextmanager
    async def _open_session(expire_on_commit: bool = False) -> AsyncGenerator[AsyncSession]:
        nonlocal schema_created
        if not schema_created:
            async with get_engine().begin() as conn:
                await conn.run_sync(lambda c: SQLModel.metadata.create_all(c, checkfirst=False))
            schema_created = True
        async with real_open_session(expire_on_commit=expire_on_commit) as s:
            yield s

    monkeypatch.setattr(core_db, "open_session", _open_session)

    try:
        yield
    finally:
        if schema_created:
            await dispose_engine()


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    """Async session on the shared in-memory database (schema from ``_db_schema``).

    Because the engine uses a ``StaticPool``, every session opened on it — this
    fixture, the request path, or a ``session_scope`` call in background/CLI code —
    shares the same database.
    """
    async with db.session_scope() as s:
        yield s


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
