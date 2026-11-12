"""Engine tests: get_accessible_scope_object_ids returning where a user holds a permission.
Authored with LLM (Claude) assistance."""

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User
from sparkth.core.permissions import get_accessible_scope_object_ids
from sparkth.core.permissions.models import (
    Group,
    GroupMembership,
    GroupRoleAssignment,
    Role,
    RoleAssignment,
    RolePermission,
)
from sparkth.lib.permissions import GROUP_READ, GROUP_UPDATE
from sparkth.lib.permissions.scopes import GLOBAL, GROUP, ROLE


async def make_user(session: AsyncSession, username: str) -> User:
    user = User(name="T", username=username, email=f"{username}@example.com", hashed_password="x")
    session.add(user)
    await session.flush()
    return user


async def make_role(session: AsyncSession, name: str, permissions: list[str]) -> Role:
    role = Role(name=name)
    session.add(role)
    await session.flush()
    assert role.id is not None
    for permission in permissions:
        session.add(RolePermission(role_id=role.id, permission=permission))
    await session.flush()
    return role


async def assign(
    session: AsyncSession, user: User, role: Role, scope: str, scope_object_id: str | None
) -> RoleAssignment:
    assert user.id is not None and role.id is not None
    assignment = RoleAssignment(user_id=user.id, role_id=role.id, scope=scope, scope_object_id=scope_object_id)
    session.add(assignment)
    await session.flush()
    return assignment


async def assign_through_group(
    session: AsyncSession, user: User, role: Role, scope: str, scope_object_id: str | None
) -> GroupMembership:
    group = Group(name=f"grp-{user.username}-{role.name}-{scope}-{scope_object_id}")
    session.add(group)
    await session.flush()
    assert group.id is not None and user.id is not None and role.id is not None
    membership = GroupMembership(user_id=user.id, group_id=group.id)
    session.add(membership)
    session.add(GroupRoleAssignment(group_id=group.id, role_id=role.id, scope=scope, scope_object_id=scope_object_id))
    await session.flush()
    return membership


async def test_returns_object_ids_of_own_assignments(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    role = await make_role(session, "reader", [GROUP_READ.name])
    await assign(session, user, role, GROUP.name, "7")
    await assign(session, user, role, GROUP.name, "13")
    assert await get_accessible_scope_object_ids(user, GROUP_READ, GROUP, session) == {"7", "13"}


async def test_returns_ids_granted_through_a_group_the_user_belongs_to(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    role = await make_role(session, "reader", [GROUP_READ.name])
    await assign_through_group(session, user, role, GROUP.name, "7")
    assert await get_accessible_scope_object_ids(user, GROUP_READ, GROUP, session) == {"7"}


async def test_global_grant_returns_none(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    role = await make_role(session, "reader", [GROUP_READ.name])
    await assign(session, user, role, GLOBAL.name, None)
    assert await get_accessible_scope_object_ids(user, GROUP_READ, GROUP, session) is None


async def test_global_grant_through_a_group_returns_none(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    role = await make_role(session, "reader", [GROUP_READ.name])
    await assign_through_group(session, user, role, GLOBAL.name, None)
    assert await get_accessible_scope_object_ids(user, GROUP_READ, GROUP, session) is None


async def test_global_grant_wins_over_object_grants(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    role = await make_role(session, "reader", [GROUP_READ.name])
    await assign(session, user, role, GLOBAL.name, None)
    await assign(session, user, role, GROUP.name, "7")
    assert await get_accessible_scope_object_ids(user, GROUP_READ, GROUP, session) is None


async def test_other_scope_and_other_permission_are_ignored(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    reader = await make_role(session, "reader", [GROUP_READ.name])
    writer = await make_role(session, "writer", [GROUP_UPDATE.name])
    await assign(session, user, reader, ROLE.name, "3")
    await assign(session, user, writer, GROUP.name, "7")
    assert await get_accessible_scope_object_ids(user, GROUP_READ, GROUP, session) == set()


async def test_other_users_grants_are_ignored(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    other = await make_user(session, "bob")
    role = await make_role(session, "reader", [GROUP_READ.name])
    await assign(session, other, role, GROUP.name, "7")
    assert await get_accessible_scope_object_ids(user, GROUP_READ, GROUP, session) == set()


async def test_revoked_assignment_contributes_nothing(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    role = await make_role(session, "reader", [GROUP_READ.name])
    assignment = await assign(session, user, role, GROUP.name, "7")
    assignment.soft_delete()
    await session.flush()
    assert await get_accessible_scope_object_ids(user, GROUP_READ, GROUP, session) == set()


async def test_removed_membership_contributes_nothing(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    role = await make_role(session, "reader", [GROUP_READ.name])
    membership = await assign_through_group(session, user, role, GROUP.name, "7")
    membership.soft_delete()
    await session.flush()
    assert await get_accessible_scope_object_ids(user, GROUP_READ, GROUP, session) == set()


async def test_revoked_group_role_assignment_contributes_nothing(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    role = await make_role(session, "reader", [GROUP_READ.name])
    membership = await assign_through_group(session, user, role, GROUP.name, "7")
    grant = (
        await session.exec(select(GroupRoleAssignment).where(GroupRoleAssignment.group_id == membership.group_id))
    ).one()
    grant.soft_delete()
    await session.flush()
    assert await get_accessible_scope_object_ids(user, GROUP_READ, GROUP, session) == set()


async def test_null_object_row_at_the_scope_is_ignored(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    role = await make_role(session, "reader", [GROUP_READ.name])
    await assign(session, user, role, GROUP.name, None)
    assert await get_accessible_scope_object_ids(user, GROUP_READ, GROUP, session) == set()


async def test_nothing_held_returns_empty_set(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    assert await get_accessible_scope_object_ids(user, GROUP_READ, GROUP, session) == set()
