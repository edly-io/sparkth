"""Tests for the user-management CLI commands (app.cli.users).

The CLI calls :func:`app.lib.db.session_scope` directly rather than going through
the ``get_async_session`` FastAPI dependency, so — following the convention used
for other ``session_scope`` consumers in the suite — we patch it to yield the
rollback-isolated test session instead of relying on the real engine.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest
import typer
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.cli import users
from app.models.permissions import Role, RoleAssignment
from app.models.user import User


# TODO we should get rid of this fixture once we properly override session_scope in
# all unit tests.
@pytest.fixture
async def cli_session(session: AsyncSession) -> AsyncGenerator[AsyncSession, None]:
    # session_scope() yields sessions with expire_on_commit=False; mirror that so
    # post-commit attribute access doesn't trigger implicit (and failing) async IO.
    session.sync_session.expire_on_commit = False

    @asynccontextmanager
    async def scope(expire_on_commit: bool = False) -> AsyncGenerator[AsyncSession, None]:
        yield session

    with patch("app.cli.users.session_scope", scope):
        yield session


async def test_create_user_persists_a_hashed_user(cli_session: AsyncSession) -> None:
    await users._create_user(
        username="alice",
        email="alice@example.com",
        password="s3cret",
        name="Alice",
        admin=False,
        email_verified=True,
    )

    user: User = (await cli_session.exec(select(User).where(User.username == "alice"))).one()
    assert user.email == "alice@example.com"
    assert user.email_verified
    assert user.email_verified_at
    assert user.hashed_password != "s3cret"


async def test_create_unverified_user(cli_session: AsyncSession) -> None:
    await users._create_user(
        username="alice",
        email="alice@example.com",
        password="s3cret",
        name="Alice",
        admin=False,
        email_verified=False,
    )

    user: User = (await cli_session.exec(select(User).where(User.username == "alice"))).one()
    assert user.email_verified is False
    assert user.email_verified_at is None


async def test_create_user_rejects_duplicate(cli_session: AsyncSession) -> None:
    await users._create_user(
        username="bob",
        email="bob@example.com",
        password="s3cret",
        name=None,
        admin=False,
        email_verified=True,
    )

    with pytest.raises(typer.Exit):
        await users._create_user(
            username="bob",
            email="other@example.com",
            password="s3cret",
            name=None,
            admin=False,
            email_verified=True,
        )


async def test_reset_password_changes_hash(cli_session: AsyncSession) -> None:
    await users._create_user(
        username="carol",
        email="carol@example.com",
        password="old-pass",
        name=None,
        admin=False,
        email_verified=True,
    )
    old_hash = (await cli_session.exec(select(User).where(User.username == "carol"))).one().hashed_password

    await users._reset_password(identifier="carol", new_password="new-pass")

    new_hash = (await cli_session.exec(select(User).where(User.username == "carol"))).one().hashed_password
    assert new_hash != old_hash


async def test_reset_password_unknown_user_exits(cli_session: AsyncSession) -> None:
    with pytest.raises(typer.Exit):
        await users._reset_password(identifier="ghost", new_password="whatever")


async def test_create_user_with_admin_assigns_admin_role(cli_session: AsyncSession) -> None:
    cli_session.add(Role(name="admin"))
    await cli_session.flush()
    await users._create_user(
        username="root",
        email="root@example.com",
        password="s3cret",
        name=None,
        admin=True,
        email_verified=True,
    )
    user = (await cli_session.exec(select(User).where(User.username == "root"))).one()
    assert user.id is not None
    assignment = (await cli_session.exec(select(RoleAssignment).where(RoleAssignment.user_id == user.id))).one()
    assert assignment.scope_type == "global"


async def test_create_user_with_admin_missing_role_exits(cli_session: AsyncSession) -> None:
    # No "admin" role seeded → assign_role raises RoleNotFound → command exits gracefully
    # (the user create + role assign share one commit, so nothing is persisted on failure).
    with pytest.raises(typer.Exit):
        await users._create_user(
            username="root",
            email="root@example.com",
            password="s3cret",
            name=None,
            admin=True,
            email_verified=True,
        )
