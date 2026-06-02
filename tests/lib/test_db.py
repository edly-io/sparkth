"""Tests for the public database-session API (app.lib.db)."""

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

import app.lib.db
from app.lib.db import session_scope


@pytest.fixture(autouse=True)
def use_test_engine(engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point session_scope at the shared in-memory test engine (tests/conftest.py).

    session_scope reads ``app.lib.db.async_engine`` at call time, so patching the
    module attribute is enough to redirect it onto the test engine.
    """
    monkeypatch.setattr(app.lib.db, "async_engine", engine)


async def test_session_scope_yields_async_session(engine: AsyncEngine) -> None:
    async with session_scope() as session:
        assert isinstance(session, AsyncSession)
        assert session.bind is engine


async def test_session_scope_defaults_to_expire_on_commit_false() -> None:
    async with session_scope() as session:
        assert session.sync_session.expire_on_commit is False


async def test_session_scope_honours_expire_on_commit_override() -> None:
    async with session_scope(expire_on_commit=True) as session:
        assert session.sync_session.expire_on_commit is True


async def test_session_scope_can_execute_a_query() -> None:
    async with session_scope() as session:
        result = await session.exec(select(1))
        assert result.one() == 1


async def test_session_scope_closes_session_on_exit() -> None:
    async with session_scope() as session:
        await session.exec(select(1))
        assert session.sync_session.in_transaction()
    # After the context exits, the session is closed and its transaction released.
    assert not session.sync_session.in_transaction()
