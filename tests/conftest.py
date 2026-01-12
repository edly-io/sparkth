from collections.abc import AsyncGenerator
from typing import Any, cast

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.db import get_session
from app.main import app
from app.models.plugin import Plugin, UserPlugin
from app.models.user import User
from app.services.plugin import PluginService, get_plugin_service

DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()


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

    app.dependency_overrides[get_session] = get_session_override

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def setup_plugins_and_user(session: AsyncSession) -> dict[str, Any]:
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
async def override_dependencies(client: AsyncClient, setup_plugins_and_user: Any) -> AsyncGenerator[AsyncClient, None]:
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


@pytest.fixture
async def current_user(client: AsyncClient) -> AsyncGenerator[User, None]:
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
