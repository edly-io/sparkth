"""Tests for get_user_permissions — the all-names sibling of can().

Same query shape as can() (active assignments at a scope, honouring the
objectless-ancestor cascade), but returns every distinct permission the user
holds instead of testing one.
"""

from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User
from sparkth.core.permissions.models import Role, RolePermission
from sparkth.lib.permissions import assign_role, get_user_permissions
from sparkth.lib.permissions.scopes import GLOBAL, WHITELIST


async def _make_user(session: AsyncSession, username: str) -> User:
    user = User(name="T", username=username, email=f"{username}@example.com", hashed_password="x")
    session.add(user)
    await session.flush()
    return user


async def _make_role(session: AsyncSession, name: str, permissions: list[str]) -> Role:
    role = Role(name=name)
    session.add(role)
    await session.flush()
    assert role.id is not None
    for permission in permissions:
        session.add(RolePermission(role_id=role.id, permission=permission))
    await session.flush()
    return role


async def test_returns_granted_names_at_scope(session: AsyncSession) -> None:
    user = await _make_user(session, "alice")
    assert user.id is not None
    await _make_role(session, "reader", ["analytics.read", "role.read"])
    await assign_role(user.id, "reader", GLOBAL, None, session)

    names = await get_user_permissions(user, GLOBAL, None, session)

    assert sorted(names) == ["analytics.read", "role.read"]


async def test_returns_empty_list_without_grants(session: AsyncSession) -> None:
    user = await _make_user(session, "bob")

    names = await get_user_permissions(user, GLOBAL, None, session)

    assert names == []


async def test_deduplicates_permission_granted_via_two_roles(session: AsyncSession) -> None:
    user = await _make_user(session, "carol")
    assert user.id is not None
    await _make_role(session, "role-a", ["analytics.read"])
    await _make_role(session, "role-b", ["analytics.read"])
    await assign_role(user.id, "role-a", GLOBAL, None, session)
    await assign_role(user.id, "role-b", GLOBAL, None, session)

    names = await get_user_permissions(user, GLOBAL, None, session)

    assert names == ["analytics.read"]


async def test_honours_scope_chain_cascade(session: AsyncSession) -> None:
    # A GLOBAL grant must satisfy a lookup at a descendant objectless scope
    # (WHITELIST), exactly like can()'s parent->child cascade.
    user = await _make_user(session, "dave")
    assert user.id is not None
    await _make_role(session, "reader", ["analytics.read"])
    await assign_role(user.id, "reader", GLOBAL, None, session)

    names = await get_user_permissions(user, WHITELIST, None, session)

    assert names == ["analytics.read"]
