import os
from collections.abc import AsyncGenerator, Generator
from typing import Any, cast
from unittest.mock import MagicMock

# Set test environment variables BEFORE importing app modules.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("RAG_MCP_URL", "http://localhost:8000")
os.environ.setdefault("LLM_ENCRYPTION_KEY", "QL9oJuLxl0gKCbJpQgkzrdlsZUmvIVR3Cp0gSPcVLvQ=")
os.environ.setdefault("SLACK_CLIENT_ID", "test-slack-client-id")
os.environ.setdefault("SLACK_CLIENT_SECRET", "test-slack-client-secret")
os.environ.setdefault("SLACK_SIGNING_SECRET", "test-slack-signing-secret")
os.environ.setdefault("SLACK_REDIRECT_URI", "http://localhost:7727/api/v1/slack/callback")

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.auth import get_current_user
from app.core_plugins.chat.routes import chat_router
from app.lib.db import get_async_session
from app.main import app  # must be imported before chat_router to avoid circular imports
from app.models.user import User

_CHAT_PREFIX = "/api/v1"
_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Register chat routes for tests.
# The plugin lifespan (which normally registers chat routes via
# `plugin_manager.load_all_enabled`) does not run in tests, so we mount
# the router directly. Same pattern as `tests/slack/conftest.py` and
# `tests/googledrive/conftest.py`.
if f"{_CHAT_PREFIX}/chat/completions" not in {getattr(r, "path", None) for r in app.routes}:
    app.include_router(chat_router, prefix=_CHAT_PREFIX)


@pytest.fixture(scope="session")
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    async_engine = create_async_engine(
        _DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield async_engine
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await async_engine.dispose()


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    async with engine.connect() as conn:
        tx = await conn.begin()
        s = AsyncSession(bind=conn)
        try:
            yield s
        finally:
            await s.close()
            await tx.rollback()


@pytest.fixture
async def client(session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def get_session_override() -> AsyncGenerator[AsyncSession, None]:
        yield session

    app.dependency_overrides[get_async_session] = get_session_override

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def current_user(client: AsyncClient) -> AsyncGenerator[User, None]:
    transport = cast(ASGITransport, client._transport)
    from fastapi import FastAPI

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


@pytest.fixture
def mock_rag_provider() -> Generator[Any, None, None]:
    from unittest.mock import patch

    with (
        patch("app.llm.providers.get_provider") as mock_get_provider,
        patch("app.core_plugins.chat.routes.dependencies.get_rag_context_service") as mock_get_rag_provider,
        patch("app.core_plugins.googledrive.utils.get_provider") as mock_get_utils_provider,
    ):
        mock_provider = MagicMock()
        mock_get_provider.return_value = mock_provider
        mock_get_rag_provider.return_value = mock_provider
        mock_get_utils_provider.return_value = mock_provider
        yield mock_get_provider


@pytest.fixture(autouse=True)
def reset_cache_service() -> Generator[None, None, None]:
    yield
    from app.core.cache import get_cache_service

    get_cache_service.cache_clear()


@pytest.fixture(autouse=True)
def stub_send_verification_email() -> Generator[Any, None, None]:
    from unittest.mock import AsyncMock, patch

    with patch("app.api.v1.auth.send_verification_email", new_callable=AsyncMock) as stub:
        yield stub
