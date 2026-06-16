"""Tests for the public database-session API (app.lib.db)."""

from sqlmodel import select

from app.lib.db import session_scope


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
