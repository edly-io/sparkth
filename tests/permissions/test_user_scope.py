"""The ``user`` scope: a user's own records live at ``user:<id>``, and the two scope-id dependencies
gate create and list routes there.
Authored with LLM (Claude) assistance."""

from collections.abc import Callable
from typing import cast

from httpx import AsyncClient
from sqlalchemy import delete
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User
from sparkth.core.permissions.models import RoleAssignment
from sparkth.lib.auth import get_current_user_id
from sparkth.lib.permissions import ROLE_READ, can, get_listed_owner_id
from sparkth.lib.permissions.scopes import USER, build_scope_path
from sparkth.lib.testing import grant_global_permission, grant_permission_at_scope, grant_permissions, make_user

P = ROLE_READ


def _path(user: User) -> str:
    return build_scope_path(USER, str(user.id))


async def _users(session: AsyncSession) -> tuple[User, User]:
    a = await make_user(session, "alice")
    b = await make_user(session, "bob")
    await session.commit()
    return a, b


async def test_user_holds_nothing_at_own_scope_without_a_grant(session: AsyncSession) -> None:
    a, _ = await _users(session)
    assert await can(a, P, USER, _path(a), session) is False


async def test_grant_at_own_scope_reaches_own_records(session: AsyncSession) -> None:
    a, b = await _users(session)
    await grant_permission_at_scope(session, cast(int, a.id), P.name, USER, str(a.id))
    await session.commit()
    assert await can(a, P, USER, _path(a), session) is True
    assert await can(a, P, USER, _path(b), session) is False


async def test_global_grant_reaches_any_user_scope(session: AsyncSession) -> None:
    a, b = await _users(session)
    await grant_global_permission(session, cast(int, b.id), P.name)
    await session.commit()
    assert await can(b, P, USER, _path(a), session) is True


async def test_own_scope_gate(session: AsyncSession, gated_client: Callable[..., AsyncClient]) -> None:
    a, _ = await _users(session)
    await grant_permission_at_scope(session, cast(int, a.id), P.name, USER, str(a.id))
    await session.commit()
    dep = P.require_for_object(USER, get_current_user_id)
    async with gated_client(dep, a) as client:
        assert (await client.get("/probe")).status_code == 200
    await session.exec(delete(RoleAssignment))
    await session.commit()
    async with gated_client(dep, a) as client:
        assert (await client.get("/probe")).status_code == 403


async def test_listed_owner_defaults_to_the_caller(
    session: AsyncSession, gated_client: Callable[..., AsyncClient]
) -> None:
    a, _ = await _users(session)
    await grant_permission_at_scope(session, cast(int, a.id), P.name, USER, str(a.id))
    await session.commit()
    dep = P.require_for_object(USER, get_listed_owner_id)
    async with gated_client(dep, a) as client:
        assert (await client.get("/probe")).status_code == 200
        assert (await client.get(f"/probe?owner_id={a.id}")).status_code == 200


async def test_listed_owner_needs_a_grant_at_that_user(
    session: AsyncSession, gated_client: Callable[..., AsyncClient]
) -> None:
    a, b = await _users(session)
    await grant_permission_at_scope(session, cast(int, b.id), P.name, USER, str(b.id))
    await session.commit()
    dep = P.require_for_object(USER, get_listed_owner_id)
    async with gated_client(dep, b) as client:
        assert (await client.get(f"/probe?owner_id={a.id}")).status_code == 403
    await grant_permissions(session, b, [P.name], USER.name, str(a.id))
    await session.commit()
    async with gated_client(dep, b) as client:
        assert (await client.get(f"/probe?owner_id={a.id}")).status_code == 200
