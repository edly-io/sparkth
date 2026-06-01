"""Re-export fixtures from tests/conftest.py for co-located tests in app/."""

# This file allows co-located test directories (e.g., app/rag/tests, app/core_plugins/*/tests)
# to access fixtures defined in the root tests/conftest.py without pytest needing to traverse
# up and out of the app/ package.

from collections.abc import AsyncGenerator, Generator
from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest.fixture(scope="session")
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create in-memory async engine for app-level tests."""
    DATABASE_URL = "sqlite+aiosqlite:///:memory:"
    eng = create_async_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await eng.dispose()


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


@pytest.fixture
async def client(session: AsyncSession) -> AsyncGenerator[Any, None]:
    """Async client with overridden session."""
    from httpx import ASGITransport, AsyncClient

    from app.core.db import get_async_session
    from app.main import app

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
async def setup_plugins_and_user(session: AsyncSession) -> dict[str, Any]:
    """Setup test plugins and user."""
    from app.models.plugin import Plugin, UserPlugin
    from app.models.user import User

    user = User(
        name="Test User", username="testuser123", email="test@example.com", hashed_password="fakehashedpassword"
    )
    session.add(user)
    await session.flush()

    plugin_a = Plugin(name="plugin_a", is_core=True, enabled=True)
    plugin_b = Plugin(name="plugin_b", is_core=True, enabled=True)
    configured_plugin_disabled = Plugin(name="configured_plugin_disabled", is_core=True, enabled=True)
    disabled_plugin = Plugin(name="disabled_plugin", is_core=True, enabled=False)
    session.add_all([plugin_a, plugin_b, configured_plugin_disabled, disabled_plugin])
    await session.flush()

    user_plugin_b = UserPlugin(
        user_id=cast(int, user.id), plugin_id=cast(int, plugin_b.id), enabled=True, config={"some config": "abc"}
    )
    session.add(user_plugin_b)
    await session.flush()

    user_plugin_c = UserPlugin(
        user_id=cast(int, user.id),
        plugin_id=cast(int, configured_plugin_disabled.id),
        enabled=False,
        config={"some config": "abc"},
    )
    session.add(user_plugin_c)
    await session.flush()

    return {"user": user, "plugins": [plugin_a, plugin_b, configured_plugin_disabled, disabled_plugin]}


@pytest.fixture
async def override_dependencies(client: Any, setup_plugins_and_user: Any) -> AsyncGenerator[Any, None]:
    """Override dependencies for testing."""
    from fastapi import FastAPI
    from httpx import ASGITransport

    from app.api.v1.auth import get_current_user
    from app.services.plugin import PluginService, get_plugin_service

    transport = cast(ASGITransport, client._transport)
    app_instance = cast(FastAPI, transport.app)
    user = setup_plugins_and_user["user"]

    async def get_user_override() -> Any:
        return user

    def get_plugin_service_override() -> PluginService:
        return PluginService()

    app_instance.dependency_overrides[get_current_user] = get_user_override
    app_instance.dependency_overrides[get_plugin_service] = get_plugin_service_override
    yield client
    app_instance.dependency_overrides.pop(get_current_user, None)
    app_instance.dependency_overrides.pop(get_plugin_service, None)


@pytest.fixture
async def current_user(client: Any) -> AsyncGenerator[Any, None]:
    """Create current user for testing."""
    from fastapi import FastAPI
    from httpx import ASGITransport

    from app.api.v1.auth import get_current_user
    from app.models.user import User

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
def reset_cache_service() -> Generator[None, None, None]:
    """Clear the get_cache_service lru_cache after each test."""
    yield
    from app.core.cache import get_cache_service

    get_cache_service.cache_clear()


@pytest.fixture(autouse=True)
def stub_send_verification_email() -> Generator[Any, None, None]:
    """Stub the verification email sender so tests don't hit SMTP."""
    from unittest.mock import AsyncMock, patch

    with patch("app.api.v1.auth.send_verification_email", new_callable=AsyncMock) as stub:
        yield stub
