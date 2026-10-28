"""Tests for the user-management CLI commands (sparkth.cli.users).

The CLI calls :func:`sparkth.lib.db.session_scope` directly rather than going through
the ``get_async_session`` FastAPI dependency. ``session_scope`` is now engine-backed,
so the CLI hits the same in-memory test database as the ``session`` fixture (they
share one ``StaticPool`` connection); no patching is needed — we just assert through
``session``.
"""

import pytest
import typer
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from typer.testing import CliRunner

from sparkth.cli import users
from sparkth.cli.main import app as root_cli
from sparkth.core.models.user import User


async def test_create_user_persists_a_hashed_user(session: AsyncSession) -> None:
    await users._create_user(
        username="alice",
        email="alice@example.com",
        password="s3cret",
        name="Alice",
        email_verified=True,
    )

    user: User = (await session.exec(select(User).where(User.username == "alice"))).one()
    assert user.email == "alice@example.com"
    assert user.email_verified
    assert user.email_verified_at
    assert user.hashed_password != "s3cret"


async def test_create_unverified_user(session: AsyncSession) -> None:
    await users._create_user(
        username="alice",
        email="alice@example.com",
        password="s3cret",
        name="Alice",
        email_verified=False,
    )

    user: User = (await session.exec(select(User).where(User.username == "alice"))).one()
    assert user.email_verified is False
    assert user.email_verified_at is None


async def test_create_user_defaults_name_to_username(session: AsyncSession) -> None:
    await users._create_user("root", "root@example.com", "s3cret", None, True)

    user = (await session.exec(select(User).where(User.username == "root"))).one()
    assert user.name == "root"


async def test_create_user_rejects_duplicate(session: AsyncSession) -> None:
    await users._create_user(
        username="bob",
        email="bob@example.com",
        password="s3cret",
        name=None,
        email_verified=True,
    )

    with pytest.raises(typer.Exit):
        await users._create_user(
            username="bob",
            email="other@example.com",
            password="s3cret",
            name=None,
            email_verified=True,
        )


async def test_reset_password_changes_hash(session: AsyncSession) -> None:
    await users._create_user(
        username="carol",
        email="carol@example.com",
        password="old-pass",
        name=None,
        email_verified=True,
    )
    old_hash = (await session.exec(select(User).where(User.username == "carol"))).one().hashed_password

    await users._reset_password(identifier="carol", new_password="new-pass")

    new_hash = (await session.exec(select(User).where(User.username == "carol"))).one().hashed_password
    assert new_hash != old_hash


async def test_reset_password_finds_the_user_by_email(session: AsyncSession) -> None:
    await users._create_user("carol", "carol@example.com", "old-pass", None, True)
    old_hash = (await session.exec(select(User).where(User.username == "carol"))).one().hashed_password

    await users._reset_password("carol@example.com", "new-pass")

    new_hash = (await session.exec(select(User).where(User.username == "carol"))).one().hashed_password
    assert new_hash != old_hash


async def test_reset_password_unknown_user_exits(session: AsyncSession) -> None:
    with pytest.raises(typer.Exit):
        await users._reset_password(identifier="ghost", new_password="whatever")


CREATE_ARGS = ["users", "create-user", "-u", "root", "-e", "root@example.com", "-p", "Sup3rSecret!"]


async def _fake_create_user(*_args: object) -> None:
    return None


def test_cli_wires_create_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sparkth.cli.users._create_user", _fake_create_user)
    assert CliRunner().invoke(root_cli, CREATE_ARGS).exit_code == 0


@pytest.mark.parametrize("flag", ["--admin", "--superuser"])
def test_create_user_rejects_an_admin_flag(monkeypatch: pytest.MonkeyPatch, flag: str) -> None:
    monkeypatch.setattr("sparkth.cli.users._create_user", _fake_create_user)
    assert CliRunner().invoke(root_cli, [*CREATE_ARGS, flag]).exit_code == 2
