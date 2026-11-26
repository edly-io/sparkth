"""Tests for reading a role's assignments and a group's members
(sparkth.core.permissions.grants and sparkth.core.permissions.groups). Authored with LLM (Claude) assistance."""

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.permissions import groups
from sparkth.core.permissions.exceptions import RoleAssignmentNotFound
from sparkth.core.permissions.grants import get_role_assignment, get_user_assignments_of_role
from sparkth.core.permissions.groups import get_group_assignments_of_role, get_group_members, get_group_role_assignment
from sparkth.lib.testing import add_role_assignment, assign_through_group, make_role, make_user


async def test_get_group_members_returns_each_membership_with_its_user(session: AsyncSession) -> None:
    alice = await make_user(session, "alice")
    bob = await make_user(session, "bob")
    group = await groups.create_group("cs-staff", None, session)
    assert alice.id is not None and bob.id is not None and group.id is not None
    await groups.add_group_member(alice.id, group.id, session)
    await groups.add_group_member(bob.id, group.id, session)
    pairs = await get_group_members(group.id, session)
    assert [(membership.user_id, user.username) for membership, user in pairs] == [
        (alice.id, "alice"),
        (bob.id, "bob"),
    ]


async def test_get_group_members_keeps_the_membership_of_a_soft_deleted_user(session: AsyncSession) -> None:
    alice = await make_user(session, "alice")
    group = await groups.create_group("cs-staff", None, session)
    assert alice.id is not None and group.id is not None
    await groups.add_group_member(alice.id, group.id, session)
    alice.soft_delete()
    await session.flush()
    pairs = await get_group_members(group.id, session)
    assert [(user.username, user.is_deleted) for _, user in pairs] == [("alice", True)]


async def test_get_user_assignments_of_role_lists_active_rows_with_users(session: AsyncSession) -> None:
    alice = await make_user(session, "alice")
    bob = await make_user(session, "bob")
    role = await make_role(session, "grader", [])
    await add_role_assignment(session, alice, role, "global", None)
    revoked = await add_role_assignment(session, bob, role, "global", None)
    revoked.soft_delete()
    await session.flush()
    assert role.id is not None
    pairs = await get_user_assignments_of_role(role.id, 50, 0, session)
    assert [(assignment.role_id, user.username) for assignment, user in pairs] == [(role.id, "alice")]


async def test_get_user_assignments_of_role_keeps_the_assignment_of_a_soft_deleted_user(
    session: AsyncSession,
) -> None:
    alice = await make_user(session, "alice")
    role = await make_role(session, "grader", [])
    await add_role_assignment(session, alice, role, "global", None)
    alice.soft_delete()
    await session.flush()
    assert role.id is not None
    pairs = await get_user_assignments_of_role(role.id, 50, 0, session)
    assert [(user.username, user.is_deleted) for _, user in pairs] == [("alice", True)]


async def test_get_user_assignments_of_role_pages(session: AsyncSession) -> None:
    role = await make_role(session, "grader", [])
    for name in ("alice", "bob", "carol"):
        await add_role_assignment(session, await make_user(session, name), role, "global", None)
    assert role.id is not None
    pairs = await get_user_assignments_of_role(role.id, 1, 1, session)
    assert [user.username for _, user in pairs] == ["bob"]


async def test_get_role_assignment_returns_the_active_row(session: AsyncSession) -> None:
    user = await make_user(session, "ada")
    role = await make_role(session, "held", [])
    assignment = await add_role_assignment(session, user, role, "global", None)
    assert assignment.id is not None and role.id is not None
    found = await get_role_assignment(assignment.id, role.id, session)
    assert found.id == assignment.id


async def test_get_role_assignment_refuses_a_revoked_row(session: AsyncSession) -> None:
    user = await make_user(session, "ada")
    role = await make_role(session, "held", [])
    assignment = await add_role_assignment(session, user, role, "global", None)
    assignment.soft_delete()
    await session.flush()
    assert assignment.id is not None and role.id is not None
    with pytest.raises(RoleAssignmentNotFound):
        await get_role_assignment(assignment.id, role.id, session)


async def test_get_role_assignment_refuses_an_id_of_another_role(session: AsyncSession) -> None:
    user = await make_user(session, "ada")
    held = await make_role(session, "held", [])
    other = await make_role(session, "other", [])
    assignment = await add_role_assignment(session, user, held, "global", None)
    assert assignment.id is not None and other.id is not None
    with pytest.raises(RoleAssignmentNotFound):
        await get_role_assignment(assignment.id, other.id, session)


async def test_get_group_assignments_of_role_lists_active_rows_with_groups(session: AsyncSession) -> None:
    user = await make_user(session, "ada")
    role = await make_role(session, "grader", [])
    _, assignment = await assign_through_group(session, user, role, "global", None)
    assert role.id is not None
    pairs = await get_group_assignments_of_role(role.id, session)
    assert [(found.id, group.name) for found, group in pairs] == [
        (assignment.id, "grp-ada-grader-global-None"),
    ]


async def test_get_group_role_assignment_refuses_an_id_of_another_role(session: AsyncSession) -> None:
    user = await make_user(session, "ada")
    held = await make_role(session, "held", [])
    other = await make_role(session, "other", [])
    _, assignment = await assign_through_group(session, user, held, "global", None)
    assert assignment.id is not None and other.id is not None
    with pytest.raises(RoleAssignmentNotFound):
        await get_group_role_assignment(assignment.id, other.id, session)


async def test_get_group_assignments_of_role_skips_a_revoked_row(session: AsyncSession) -> None:
    user = await make_user(session, "ada")
    role = await make_role(session, "grader", [])
    _, assignment = await assign_through_group(session, user, role, "global", None)
    assignment.soft_delete()
    await session.flush()
    assert role.id is not None
    assert await get_group_assignments_of_role(role.id, session) == []


async def test_get_group_role_assignment_returns_the_active_row(session: AsyncSession) -> None:
    user = await make_user(session, "ada")
    role = await make_role(session, "held", [])
    _, assignment = await assign_through_group(session, user, role, "global", None)
    assert assignment.id is not None and role.id is not None
    found = await get_group_role_assignment(assignment.id, role.id, session)
    assert found.id == assignment.id


async def test_get_group_role_assignment_refuses_a_revoked_row(session: AsyncSession) -> None:
    user = await make_user(session, "ada")
    role = await make_role(session, "held", [])
    _, assignment = await assign_through_group(session, user, role, "global", None)
    assignment.soft_delete()
    await session.flush()
    assert assignment.id is not None and role.id is not None
    with pytest.raises(RoleAssignmentNotFound):
        await get_group_role_assignment(assignment.id, role.id, session)
