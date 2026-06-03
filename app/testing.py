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
os.environ.setdefault("RAG_MCP_URL", "http://localhost:8000")
os.environ.setdefault("LLM_ENCRYPTION_KEY", "QL9oJuLxl0gKCbJpQgkzrdlsZUmvIVR3Cp0gSPcVLvQ=")

from collections.abc import AsyncGenerator, Generator
from typing import Any, cast


import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.auth import get_current_user
from app.models.plugin import Plugin, UserPlugin
from app.models.user import User
from app.services.plugin import PluginService, get_plugin_service
from tests.lib.env import TEST_DATABASE_URL
from tests.lib.fixtures import (  # noqa: F401 — re-exported for pytest discovery
    client,
    current_user,
    mock_rag_provider,
    reset_cache_service,
    session,
    stub_send_verification_email,
)


@pytest.fixture(scope="session")
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()


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
    sess = Session(bind=connection)
    try:
        yield sess
    finally:
        sess.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
async def setup_plugins_and_user(session: AsyncSession) -> dict[str, Any]:  # noqa: F811
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
async def override_dependencies(client: AsyncClient, setup_plugins_and_user: Any) -> AsyncGenerator[AsyncClient, None]:  # noqa: F811
    transport = cast(ASGITransport, client._transport)
    app_instance = cast(FastAPI, transport.app)
    user: User = setup_plugins_and_user["user"]

    async def get_user_override() -> User:
        return user

    def get_plugin_service_override() -> PluginService:
        return PluginService()

    app_instance.dependency_overrides[get_current_user] = get_user_override
    app_instance.dependency_overrides[get_plugin_service] = get_plugin_service_override
    yield client
    app_instance.dependency_overrides.pop(get_current_user, None)
    app_instance.dependency_overrides.pop(get_plugin_service, None)
