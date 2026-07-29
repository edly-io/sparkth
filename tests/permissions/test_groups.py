"""Tests for the group tables and the group engine functions
(sparkth.core.permissions.groups). Authored with LLM (Claude) assistance."""

from collections.abc import Awaitable, Callable
from functools import partial
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User
from sparkth.core.permissions import groups
from sparkth.core.permissions.exceptions import (
    GroupAlreadyExists,
    GroupInUse,
    GroupNotFound,
    InvalidScopeObjectId,
    RoleNotFound,
)
from sparkth.core.permissions.models import Group, GroupMembership, GroupRoleAssignment, Role, RolePermission
from sparkth.lib.permissions import Permission, can
from sparkth.lib.permissions.scopes import GLOBAL


async def test_group_round_trips(session: AsyncSession) -> None:
    group = Group(name="cs-staff", description="CS department staff")
    session.add(group)
    await session.flush()
    assert group.id is not None
    assert group.name == "cs-staff"
    assert group.description == "CS department staff"


async def test_group_membership_round_trips_with_manual_source(session: AsyncSession) -> None:
    group = Group(name="cs-staff")
    session.add(group)
    await session.flush()
    assert group.id is not None

    membership = GroupMembership(user_id=1, group_id=group.id)
    session.add(membership)
    await session.flush()
    assert membership.id is not None
    assert membership.source == "manual"
    assert membership.is_deleted is False


async def test_duplicate_active_membership_is_rejected(session: AsyncSession) -> None:
    group = Group(name="cs-staff")
    session.add(group)
    await session.flush()
    assert group.id is not None
    session.add(GroupMembership(user_id=1, group_id=group.id))
    await session.flush()
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(GroupMembership(user_id=1, group_id=group.id))


async def test_soft_deleted_membership_does_not_block_readd(session: AsyncSession) -> None:
    group = Group(name="cs-staff")
    session.add(group)
    await session.flush()
    assert group.id is not None
    removed = GroupMembership(user_id=1, group_id=group.id)
    session.add(removed)
    await session.flush()
    removed.soft_delete()
    await session.flush()
    session.add(GroupMembership(user_id=1, group_id=group.id))
    await session.flush()


async def test_group_role_assignment_round_trips(session: AsyncSession) -> None:
    group = Group(name="cs-staff")
    session.add(group)
    await session.flush()
    assert group.id is not None
    assignment = GroupRoleAssignment(group_id=group.id, role_id=1, scope=GLOBAL.name, scope_object_id=None)
    session.add(assignment)
    await session.flush()
    assert assignment.id is not None
    assert assignment.is_deleted is False


async def test_duplicate_active_group_assignment_is_rejected(session: AsyncSession) -> None:
    group = Group(name="cs-staff")
    session.add(group)
    await session.flush()
    assert group.id is not None
    session.add(GroupRoleAssignment(group_id=group.id, role_id=1, scope=GLOBAL.name, scope_object_id=None))
    await session.flush()
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(GroupRoleAssignment(group_id=group.id, role_id=1, scope=GLOBAL.name, scope_object_id=None))


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


_EMPTY_RESULT = SimpleNamespace(first=lambda: None)


async def _exec_hiding_first_call(
    statement: object,
    real_exec: Callable[..., Awaitable[object]],
    state: dict[str, bool],
) -> object:
    """``session.exec`` stand-in for race tests.

    The first call (the duplicate-name pre-check) sees an empty result; later calls
    delegate — simulating a concurrent create/rename committing between check and insert.
    """
    if not state["hidden"]:
        state["hidden"] = True
        return _EMPTY_RESULT
    return await real_exec(statement)


def _hide_duplicate_check(session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the session's next exec (the duplicate-name check) see nothing."""
    fake = partial(_exec_hiding_first_call, real_exec=session.exec, state={"hidden": False})
    monkeypatch.setattr(session, "exec", fake)


def test_group_exceptions_share_name_attribute() -> None:
    assert GroupNotFound("cs-staff").name == "cs-staff"
    assert GroupAlreadyExists("cs-staff").name == "cs-staff"


async def test_create_group_persists(session: AsyncSession) -> None:
    group = await groups.create_group("cs-staff", "CS staff", session)
    assert group.id is not None
    assert group.name == "cs-staff"


async def test_create_group_duplicate_name_raises(session: AsyncSession) -> None:
    await groups.create_group("cs-staff", None, session)
    with pytest.raises(GroupAlreadyExists):
        await groups.create_group("cs-staff", None, session)


async def test_create_group_race_raises_group_already_exists(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await groups.create_group("cs-staff", None, session)
    # Hide the winner from the pre-insert check so the unique index fires — as if a
    # concurrent create committed between the check and the insert.
    _hide_duplicate_check(session, monkeypatch)
    with pytest.raises(GroupAlreadyExists):
        await groups.create_group("cs-staff", None, session)


async def test_update_group_rename_race_raises_group_already_exists(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await groups.create_group("taken", None, session)
    group = await groups.create_group("cs-staff", None, session)
    assert group.id is not None
    _hide_duplicate_check(session, monkeypatch)
    with pytest.raises(GroupAlreadyExists):
        await groups.update_group(group.id, "taken", None, session)


async def test_get_group_missing_raises(session: AsyncSession) -> None:
    with pytest.raises(GroupNotFound):
        await groups.get_group(999, session)


async def test_get_group_by_name_returns_it(session: AsyncSession) -> None:
    created = await groups.create_group("cs-staff", None, session)
    fetched = await groups.get_group_by_name("cs-staff", session)
    assert fetched.id == created.id


async def test_get_group_by_name_missing_raises(session: AsyncSession) -> None:
    with pytest.raises(GroupNotFound):
        await groups.get_group_by_name("nope", session)


async def test_list_groups_returns_all(session: AsyncSession) -> None:
    await groups.create_group("a", None, session)
    await groups.create_group("b", None, session)
    assert {g.name for g in await groups.list_groups(session)} == {"a", "b"}


async def test_update_group_changes_fields(session: AsyncSession) -> None:
    group = await groups.create_group("cs-staff", None, session)
    assert group.id is not None
    updated = await groups.update_group(group.id, "cs-staff2", "desc", session)
    assert updated.name == "cs-staff2"
    assert updated.description == "desc"


async def test_update_group_duplicate_name_raises(session: AsyncSession) -> None:
    await groups.create_group("taken", None, session)
    group = await groups.create_group("cs-staff", None, session)
    assert group.id is not None
    with pytest.raises(GroupAlreadyExists):
        await groups.update_group(group.id, "taken", None, session)


async def test_add_member_is_idempotent(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    group = await groups.create_group("cs-staff", None, session)
    assert user.id is not None and group.id is not None
    first = await groups.add_group_member(user.id, group.id, session)
    second = await groups.add_group_member(user.id, group.id, session)
    assert first.id == second.id
    assert first.source == "manual"


async def test_add_member_missing_group_raises(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    assert user.id is not None
    with pytest.raises(GroupNotFound):
        await groups.add_group_member(user.id, 999, session)


async def test_remove_member_soft_deletes(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    group = await groups.create_group("cs-staff", None, session)
    assert user.id is not None and group.id is not None
    await groups.add_group_member(user.id, group.id, session)
    await groups.remove_group_member(user.id, group.id, session)
    assert await groups.get_group_members(group.id, session) == []
    # History is retained, not hard-deleted.
    rows = (await session.exec(select(GroupMembership).where(GroupMembership.group_id == group.id))).all()
    assert len(rows) == 1 and rows[0].is_deleted is True


async def test_remove_member_noop_when_absent(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    group = await groups.create_group("cs-staff", None, session)
    assert user.id is not None and group.id is not None
    await groups.remove_group_member(user.id, group.id, session)


async def test_get_group_members_lists_active(session: AsyncSession) -> None:
    alice = await make_user(session, "alice")
    bob = await make_user(session, "bob")
    group = await groups.create_group("cs-staff", None, session)
    assert alice.id is not None and bob.id is not None and group.id is not None
    await groups.add_group_member(alice.id, group.id, session)
    await groups.add_group_member(bob.id, group.id, session)
    assert sorted(await groups.get_group_members(group.id, session)) == sorted([alice.id, bob.id])


async def test_assign_role_to_group_grants_members_access(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    group = await groups.create_group("graders", None, session)
    await make_role(session, "grader", ["assignment.grade"])
    assert user.id is not None and group.id is not None
    await groups.add_group_member(user.id, group.id, session)
    await groups.assign_role_to_group(group.id, "grader", GLOBAL, None, session)
    assert await can(user, Permission("assignment.grade"), GLOBAL, None, session) is True


async def test_assign_role_to_group_is_idempotent(session: AsyncSession) -> None:
    group = await groups.create_group("graders", None, session)
    await make_role(session, "grader", [])
    assert group.id is not None
    first = await groups.assign_role_to_group(group.id, "grader", GLOBAL, None, session)
    second = await groups.assign_role_to_group(group.id, "grader", GLOBAL, None, session)
    assert first.id == second.id


async def test_assign_role_to_group_unknown_role_raises(session: AsyncSession) -> None:
    group = await groups.create_group("graders", None, session)
    assert group.id is not None
    with pytest.raises(RoleNotFound):
        await groups.assign_role_to_group(group.id, "nope", GLOBAL, None, session)


async def test_assign_role_to_group_missing_group_raises(session: AsyncSession) -> None:
    await make_role(session, "grader", [])
    with pytest.raises(GroupNotFound):
        await groups.assign_role_to_group(999, "grader", GLOBAL, None, session)


async def test_assign_role_to_group_rejects_object_id_on_objectless_scope(session: AsyncSession) -> None:
    group = await groups.create_group("graders", None, session)
    await make_role(session, "grader", [])
    assert group.id is not None
    with pytest.raises(InvalidScopeObjectId):
        await groups.assign_role_to_group(group.id, "grader", GLOBAL, "42", session)


async def test_revoke_role_from_group_drops_access(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    group = await groups.create_group("graders", None, session)
    await make_role(session, "grader", ["assignment.grade"])
    assert user.id is not None and group.id is not None
    await groups.add_group_member(user.id, group.id, session)
    await groups.assign_role_to_group(group.id, "grader", GLOBAL, None, session)
    await groups.revoke_role_from_group(group.id, "grader", GLOBAL, None, session)
    assert await can(user, Permission("assignment.grade"), GLOBAL, None, session) is False


async def test_get_group_roles_lists_active(session: AsyncSession) -> None:
    group = await groups.create_group("graders", None, session)
    await make_role(session, "grader", [])
    assert group.id is not None
    await groups.assign_role_to_group(group.id, "grader", GLOBAL, None, session)
    role_assignments = await groups.get_group_roles(group.id, session)
    assert len(role_assignments) == 1
    assert role_assignments[0].scope == GLOBAL.name


async def test_delete_group_blocked_by_active_assignment(session: AsyncSession) -> None:
    group = await groups.create_group("graders", None, session)
    await make_role(session, "grader", [])
    assert group.id is not None
    await groups.assign_role_to_group(group.id, "grader", GLOBAL, None, session)
    with pytest.raises(GroupInUse):
        await groups.delete_group(group.id, session)


async def test_delete_group_removes_membership_history(session: AsyncSession) -> None:
    # Members alone do not block deletion; membership rows go with the group.
    user = await make_user(session, "alice")
    group = await groups.create_group("cs-staff", None, session)
    assert user.id is not None and group.id is not None
    await groups.add_group_member(user.id, group.id, session)
    await groups.delete_group(group.id, session)
    with pytest.raises(GroupNotFound):
        await groups.get_group(group.id, session)
    rows = (await session.exec(select(GroupMembership).where(GroupMembership.group_id == group.id))).all()
    assert rows == []


async def test_delete_group_removes_assignment_history(session: AsyncSession) -> None:
    # Revoked (soft-deleted) assignments do not block deletion; their rows go with the group.
    group = await groups.create_group("graders", None, session)
    await make_role(session, "grader", [])
    assert group.id is not None
    await groups.assign_role_to_group(group.id, "grader", GLOBAL, None, session)
    await groups.revoke_role_from_group(group.id, "grader", GLOBAL, None, session)
    await groups.delete_group(group.id, session)
    rows = (await session.exec(select(GroupRoleAssignment).where(GroupRoleAssignment.group_id == group.id))).all()
    assert rows == []


async def test_delete_group_missing_raises(session: AsyncSession) -> None:
    with pytest.raises(GroupNotFound):
        await groups.delete_group(999, session)


def test_group_permissions_are_registered() -> None:
    from sparkth.lib.permissions import GROUP_CREATE, GROUP_DELETE, GROUP_READ, GROUP_UPDATE, get_permission

    assert get_permission("group.create") is GROUP_CREATE
    assert get_permission("group.read") is GROUP_READ
    assert get_permission("group.update") is GROUP_UPDATE
    assert get_permission("group.delete") is GROUP_DELETE
