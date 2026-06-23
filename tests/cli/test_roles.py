from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest
import typer
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.cli import roles
from app.core.permissions.models import Role, RoleAssignment
from app.models.user import User


@pytest.fixture
async def cli_session(session: AsyncSession) -> AsyncGenerator[AsyncSession, None]:
    session.sync_session.expire_on_commit = False

    @asynccontextmanager
    async def scope(expire_on_commit: bool = False) -> AsyncGenerator[AsyncSession, None]:
        yield session

    with patch("app.cli.roles.session_scope", scope):
        yield session


async def _seed_user_and_role(session: AsyncSession) -> None:
    session.add(User(name="A", username="alice", email="alice@e.com", hashed_password="x"))
    session.add(Role(name="admin"))
    await session.flush()


async def test_assign_role_creates_assignment(cli_session: AsyncSession) -> None:
    await _seed_user_and_role(cli_session)

    await roles._assign_role("alice", "admin", "global", None)

    assignment = (await cli_session.exec(select(RoleAssignment))).one()
    assert assignment.scope == "global"


async def test_assign_role_unknown_user_exits(cli_session: AsyncSession) -> None:
    cli_session.add(Role(name="admin"))
    await cli_session.flush()
    with pytest.raises(typer.Exit):
        await roles._assign_role("ghost", "admin", "global", None)


async def test_assign_role_unknown_role_exits(cli_session: AsyncSession) -> None:
    cli_session.add(User(name="A", username="alice", email="alice@e.com", hashed_password="x"))
    await cli_session.flush()
    with pytest.raises(typer.Exit):
        await roles._assign_role("alice", "nope", "global", None)


async def test_assign_role_non_global_scope_without_id_exits(cli_session: AsyncSession) -> None:
    await _seed_user_and_role(cli_session)
    with pytest.raises(typer.Exit):
        await roles._assign_role("alice", "admin", "course", None)
    # the dangling (scope="course", scope_object_id=NULL) row must not be created
    assert (await cli_session.exec(select(RoleAssignment))).all() == []
