from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

from app.core_plugins.chat.routes import chat_router
from app.lib.db import get_async_session
from app.main import app  # must be imported before chat_router to avoid circular imports
from tests.lib.env import TEST_DATABASE_URL  # also sets env vars as a side effect
from tests.lib.fixtures import (  # noqa: F401 — re-exported for pytest discovery
    client,
    current_user,
    mock_rag_provider,
    reset_cache_service,
    session,
    stub_send_verification_email,
)
from tests.lib.routes import register_router

register_router(app, chat_router, sentinel_path="/api/v1/chat/completions", prefix="/api/v1")


@pytest.fixture(scope="session")
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    async_engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield async_engine
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await async_engine.dispose()
