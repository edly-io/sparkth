"""Tests for resolving a CLI user argument (sparkth/cli/user_lookup.py).
Authored with LLM (Claude) assistance."""

import pytest
import typer
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.cli.user_lookup import resolve_user
from sparkth.core.models.user import User


async def _seed_user(session: AsyncSession) -> User:
    user = User(name="A", username="alice", email="alice@example.com", hashed_password="x")
    session.add(user)
    await session.flush()
    return user


async def test_resolve_user_finds_a_user_by_username(session: AsyncSession) -> None:
    user = await _seed_user(session)
    assert (await resolve_user("alice", session)).id == user.id


async def test_resolve_user_finds_a_user_by_email(session: AsyncSession) -> None:
    user = await _seed_user(session)
    assert (await resolve_user("alice@example.com", session)).id == user.id


async def test_resolve_user_exits_when_no_user_matches(
    session: AsyncSession, capsys: pytest.CaptureFixture[str]
) -> None:
    await _seed_user(session)
    with pytest.raises(typer.Exit) as excinfo:
        await resolve_user("nobody", session)
    assert excinfo.value.exit_code == 1
    assert "User 'nobody' not found!" in capsys.readouterr().out


async def test_resolve_user_exits_when_a_username_equals_another_users_email(
    session: AsyncSession, capsys: pytest.CaptureFixture[str]
) -> None:
    session.add(User(name="A", username="alice", email="shared@example.com", hashed_password="x"))
    session.add(User(name="B", username="shared@example.com", email="b@example.com", hashed_password="x"))
    await session.flush()
    with pytest.raises(typer.Exit) as excinfo:
        await resolve_user("shared@example.com", session)
    assert excinfo.value.exit_code == 1
    assert "'shared@example.com' matches more than one user" in capsys.readouterr().out
