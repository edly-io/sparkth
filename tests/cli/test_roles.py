from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest
import typer
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.cli import roles
from sparkth.core.permissions.models import Role, RoleAssignment
from sparkth.models.user import User


@pytest.fixture
async def cli_session(session: AsyncSession) -> AsyncGenerator[AsyncSession, None]:
    session.sync_session.expire_on_commit = False

    @asynccontextmanager
    async def scope(expire_on_commit: bool = False) -> AsyncGenerator[AsyncSession, None]:
        yield session

    with patch("sparkth.cli.roles.session_scope", scope):
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
    # "course" is not a registered scope kind app-wide, so this now exits via get_permission_scope
    # raising PermissionScopeNotFound — the pairing check never runs. The dangling
    # (scope="course", scope_object_id=NULL) row must still not be created.
    with pytest.raises(typer.Exit):
        await roles._assign_role("alice", "admin", "course", None)
    assert (await cli_session.exec(select(RoleAssignment))).all() == []


async def test_assign_role_global_scope_with_id_exits(cli_session: AsyncSession) -> None:
    await _seed_user_and_role(cli_session)
    # "global" is objectless; passing an id is a contradiction now caught via the engine's
    # InvalidScopeObjectId, not a hardcoded CLI pairing check. The contradictory
    # (scope="global", scope_object_id="42") row must not be created.
    with pytest.raises(typer.Exit):
        await roles._assign_role("alice", "admin", "global", "42")
    assert (await cli_session.exec(select(RoleAssignment))).all() == []


async def test_assign_role_unknown_scope_exits(cli_session: AsyncSession) -> None:
    await _seed_user_and_role(cli_session)
    # "corse" is not a registered scope kind (typo for "course"); it must be rejected
    # rather than silently persisting a no-op assignment.
    with pytest.raises(typer.Exit):
        await roles._assign_role("alice", "admin", "corse", "42")
    assert (await cli_session.exec(select(RoleAssignment))).all() == []


async def test_assign_role_objectless_whitelist_scope_no_id_succeeds(cli_session: AsyncSession) -> None:
    await _seed_user_and_role(cli_session)
    await roles._assign_role("alice", "admin", "whitelist", None)
    assignment = (await cli_session.exec(select(RoleAssignment))).one()
    assert assignment.scope == "whitelist"
    assert assignment.scope_object_id is None


async def test_assign_role_object_bearing_role_scope_with_id_succeeds(cli_session: AsyncSession) -> None:
    # The role scope is object-bearing: delegating management of one role (issue #490) is done with
    # --scope role --scope-object-id <role id>. This is the documented delegation command; the id is
    # stored verbatim (scope_object_id is polymorphic, not a foreign key).
    await _seed_user_and_role(cli_session)
    await roles._assign_role("alice", "admin", "role", "5")
    assignment = (await cli_session.exec(select(RoleAssignment))).one()
    assert assignment.scope == "role"
    assert assignment.scope_object_id == "5"


async def test_assign_role_objectless_whitelist_scope_with_id_exits(cli_session: AsyncSession) -> None:
    await _seed_user_and_role(cli_session)
    # whitelist is objectless — passing --scope-object-id is a contradiction and must be rejected
    # cleanly (not an uncaught InvalidScopeObjectId), and must persist no row.
    with pytest.raises(typer.Exit):
        await roles._assign_role("alice", "admin", "whitelist", "42")
    assert (await cli_session.exec(select(RoleAssignment))).all() == []
