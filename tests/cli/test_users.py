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

from sparkth.cli import users
from sparkth.core.permissions.models import Role
from sparkth.lib.permissions import has_role
from sparkth.lib.permissions.scopes import GLOBAL
from sparkth.models.user import User


async def test_create_user_persists_a_hashed_user(session: AsyncSession) -> None:
    await users._create_user(
        username="alice",
        email="alice@example.com",
        password="s3cret",
        name="Alice",
        superuser=False,
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
        superuser=False,
        email_verified=False,
    )

    user: User = (await session.exec(select(User).where(User.username == "alice"))).one()
    assert user.email_verified is False
    assert user.email_verified_at is None


async def test_create_user_admin_assigns_admin_role(session: AsyncSession) -> None:
    session.add(Role(name="admin"))
    await session.flush()

    await users._create_user(
        username="root",
        email="root@example.com",
        password="s3cret",
        name=None,
        superuser=True,
        email_verified=True,
    )

    user = (await session.exec(select(User).where(User.username == "root"))).one()
    assert user.name == "root"  # falls back to username when name is omitted
    assert await has_role(user, "admin", GLOBAL, None, session) is True


async def test_create_user_admin_without_seeded_role_persists_nothing(session: AsyncSession) -> None:
    # The admin role has not been seeded, so the role assignment fails. Because the
    # role is assigned before the single commit, the user must not be left orphaned.
    with pytest.raises(typer.Exit):
        await users._create_user(
            username="root",
            email="root@example.com",
            password="s3cret",
            name=None,
            superuser=True,
            email_verified=True,
        )

    assert (await session.exec(select(User).where(User.username == "root"))).all() == []


async def test_create_user_rejects_duplicate(session: AsyncSession) -> None:
    await users._create_user(
        username="bob",
        email="bob@example.com",
        password="s3cret",
        name=None,
        superuser=False,
        email_verified=True,
    )

    with pytest.raises(typer.Exit):
        await users._create_user(
            username="bob",
            email="other@example.com",
            password="s3cret",
            name=None,
            superuser=False,
            email_verified=True,
        )


async def test_reset_password_changes_hash(session: AsyncSession) -> None:
    await users._create_user(
        username="carol",
        email="carol@example.com",
        password="old-pass",
        name=None,
        superuser=False,
        email_verified=True,
    )
    old_hash = (await session.exec(select(User).where(User.username == "carol"))).one().hashed_password

    await users._reset_password(identifier="carol", new_password="new-pass")

    new_hash = (await session.exec(select(User).where(User.username == "carol"))).one().hashed_password
    assert new_hash != old_hash


async def test_reset_password_unknown_user_exits(session: AsyncSession) -> None:
    with pytest.raises(typer.Exit):
        await users._reset_password(identifier="ghost", new_password="whatever")
