"""Engine tests: get_accessible_scope_object_ids returning where a user holds a permission.
Authored with LLM (Claude) assistance."""

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.permissions.engine import get_accessible_scope_object_ids
from sparkth.core.permissions.models import GroupRoleAssignment
from sparkth.lib.permissions import GROUP_READ
from sparkth.lib.permissions.scopes import GLOBAL, GROUP, ROLE
from sparkth.lib.testing import assign, assign_through_group, make_role, make_user


async def test_returns_object_ids_of_own_assignments(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    role = await make_role(session, "reader", ["group.read"])
    await assign(session, user, role, GROUP.name, "7")
    await assign(session, user, role, GROUP.name, "13")
    assert await get_accessible_scope_object_ids(user, GROUP_READ, GROUP, session) == {"7", "13"}


async def test_returns_ids_granted_through_a_group_the_user_belongs_to(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    role = await make_role(session, "reader", ["group.read"])
    await assign_through_group(session, user, role, GROUP.name, "7")
    assert await get_accessible_scope_object_ids(user, GROUP_READ, GROUP, session) == {"7"}


async def test_global_grant_returns_none(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    role = await make_role(session, "reader", ["group.read"])
    await assign(session, user, role, GLOBAL.name, None)
    assert await get_accessible_scope_object_ids(user, GROUP_READ, GROUP, session) is None


async def test_global_grant_through_a_group_returns_none(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    role = await make_role(session, "reader", ["group.read"])
    await assign_through_group(session, user, role, GLOBAL.name, None)
    assert await get_accessible_scope_object_ids(user, GROUP_READ, GROUP, session) is None


async def test_global_grant_wins_over_object_grants(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    role = await make_role(session, "reader", ["group.read"])
    await assign(session, user, role, GLOBAL.name, None)
    await assign(session, user, role, GROUP.name, "7")
    assert await get_accessible_scope_object_ids(user, GROUP_READ, GROUP, session) is None


async def test_other_scope_and_other_permission_are_ignored(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    reader = await make_role(session, "reader", ["group.read"])
    writer = await make_role(session, "writer", ["group.update"])
    await assign(session, user, reader, ROLE.name, "3")
    await assign(session, user, writer, GROUP.name, "7")
    assert await get_accessible_scope_object_ids(user, GROUP_READ, GROUP, session) == set()


async def test_other_users_grants_are_ignored(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    other = await make_user(session, "bob")
    role = await make_role(session, "reader", ["group.read"])
    await assign(session, other, role, GROUP.name, "7")
    assert await get_accessible_scope_object_ids(user, GROUP_READ, GROUP, session) == set()


async def test_revoked_assignment_contributes_nothing(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    role = await make_role(session, "reader", ["group.read"])
    assignment = await assign(session, user, role, GROUP.name, "7")
    assignment.soft_delete()
    await session.flush()
    assert await get_accessible_scope_object_ids(user, GROUP_READ, GROUP, session) == set()


async def test_removed_membership_contributes_nothing(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    role = await make_role(session, "reader", ["group.read"])
    membership = await assign_through_group(session, user, role, GROUP.name, "7")
    membership.soft_delete()
    await session.flush()
    assert await get_accessible_scope_object_ids(user, GROUP_READ, GROUP, session) == set()


async def test_revoked_group_role_assignment_contributes_nothing(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    role = await make_role(session, "reader", ["group.read"])
    membership = await assign_through_group(session, user, role, GROUP.name, "7")
    grant = (
        await session.exec(select(GroupRoleAssignment).where(GroupRoleAssignment.group_id == membership.group_id))
    ).one()
    grant.soft_delete()
    await session.flush()
    assert await get_accessible_scope_object_ids(user, GROUP_READ, GROUP, session) == set()


async def test_null_object_row_at_the_scope_is_ignored(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    role = await make_role(session, "reader", ["group.read"])
    await assign(session, user, role, GROUP.name, None)
    assert await get_accessible_scope_object_ids(user, GROUP_READ, GROUP, session) == set()


async def test_nothing_held_returns_empty_set(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    assert await get_accessible_scope_object_ids(user, GROUP_READ, GROUP, session) == set()
