"""Tests for the role-CRUD engine functions (sparkth.core.permissions.roles)."""

from collections.abc import Awaitable, Callable

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.permissions import roles
from sparkth.core.permissions.enums import PermissionRisk
from sparkth.core.permissions.exceptions import (
    PermissionNotFound,
    RoleAlreadyExists,
    RoleIsBuiltin,
    RoleNotFound,
)
from sparkth.core.permissions.models import Group, GroupRoleAssignment, Role, RoleAssignment, RolePermission
from sparkth.core.permissions.types import RoleAssigneeCounts
from sparkth.lib.permissions import (
    assign_role,
    assign_role_to_group,
    has_role,
    revoke_role,
    revoke_role_from_group,
)
from sparkth.lib.permissions.scopes import GLOBAL, ROLE
from sparkth.lib.testing import AuditEventsFetcher, add_role_assignment, assign_through_group, make_user


async def make_group(session: AsyncSession, name: str) -> Group:
    group = Group(name=name)
    session.add(group)
    await session.flush()
    return group


async def test_create_role_persists(session: AsyncSession) -> None:
    role = await roles.create_role("grader", "Grades stuff", session)
    assert role.id is not None
    assert role.name == "grader"
    assert role.description == "Grades stuff"


async def test_create_role_duplicate_name_raises(session: AsyncSession) -> None:
    await roles.create_role("grader", None, session)
    with pytest.raises(RoleAlreadyExists):
        await roles.create_role("grader", None, session)


async def test_get_role_returns_it(session: AsyncSession) -> None:
    created = await roles.create_role("grader", None, session)
    assert created.id is not None
    fetched = await roles.get_role(created.id, session)
    assert fetched.id == created.id


async def test_get_role_missing_raises(session: AsyncSession) -> None:
    with pytest.raises(RoleNotFound):
        await roles.get_role(999, session)


async def test_list_roles_returns_all(session: AsyncSession) -> None:
    await roles.create_role("a", None, session)
    await roles.create_role("b", None, session)
    result = await roles.list_roles(None, session)
    assert {r.name for r in result} == {"a", "b"}


async def test_list_roles_filters_to_the_given_ids_in_id_order(session: AsyncSession) -> None:
    first = await roles.create_role("a", None, session)
    await roles.create_role("b", None, session)
    third = await roles.create_role("c", None, session)
    assert first.id is not None and third.id is not None
    result = await roles.list_roles({third.id, first.id}, session)
    assert [r.name for r in result] == ["a", "c"]


async def test_list_roles_with_an_empty_filter_returns_nothing(session: AsyncSession) -> None:
    await roles.create_role("a", None, session)
    assert await roles.list_roles(set(), session) == []


async def test_update_role_changes_fields(session: AsyncSession) -> None:
    role = await roles.create_role("grader", None, session)
    assert role.id is not None
    updated = await roles.update_role(role.id, "grader2", "desc", session)
    assert updated.name == "grader2"
    assert updated.description == "desc"


async def test_update_role_missing_raises(session: AsyncSession) -> None:
    with pytest.raises(RoleNotFound):
        await roles.update_role(999, "x", None, session)


async def test_update_role_duplicate_name_raises(session: AsyncSession) -> None:
    await roles.create_role("taken", None, session)
    role = await roles.create_role("grader", None, session)
    assert role.id is not None
    with pytest.raises(RoleAlreadyExists):
        await roles.update_role(role.id, "taken", None, session)


async def test_delete_role_removes_it_and_its_grants(session: AsyncSession) -> None:
    role = await roles.create_role("grader", None, session)
    assert role.id is not None
    await roles.set_role_permissions(role.id, ["assignment.grade"], session)
    await roles.delete_role(role.id, session)
    assert (await session.exec(select(Role).where(Role.id == role.id))).first() is None
    assert (await session.exec(select(RolePermission).where(RolePermission.role_id == role.id))).all() == []


async def test_delete_role_missing_raises(session: AsyncSession) -> None:
    with pytest.raises(RoleNotFound):
        await roles.delete_role(999, session)


async def test_delete_role_removes_active_assignments(session: AsyncSession) -> None:
    role = await roles.create_role("grader", None, session)
    user = await make_user(session, "alice")
    assert role.id is not None and user.id is not None
    session.add(RoleAssignment(user_id=user.id, role_id=role.id, scope=GLOBAL.name, scope_object_id=None))
    await session.flush()
    await roles.delete_role(role.id, session)
    assert (await session.exec(select(RoleAssignment).where(RoleAssignment.role_id == role.id))).all() == []


async def test_delete_role_removes_group_assignments_of_it(session: AsyncSession) -> None:
    role = await roles.create_role("grader", None, session)
    active_group = await make_group(session, "staff")
    revoked_group = await make_group(session, "alumni")
    assert role.id is not None and active_group.id is not None and revoked_group.id is not None
    revoked = GroupRoleAssignment(group_id=revoked_group.id, role_id=role.id, scope=GLOBAL.name, scope_object_id=None)
    revoked.soft_delete()
    session.add(GroupRoleAssignment(group_id=active_group.id, role_id=role.id, scope=GLOBAL.name, scope_object_id=None))
    session.add(revoked)
    await session.flush()
    await roles.delete_role(role.id, session)
    assert (await session.exec(select(GroupRoleAssignment).where(GroupRoleAssignment.role_id == role.id))).all() == []


async def test_delete_role_allowed_when_only_soft_deleted_assignment(session: AsyncSession) -> None:
    role = await roles.create_role("grader", None, session)
    user = await make_user(session, "alice")
    assert role.id is not None and user.id is not None
    assignment = RoleAssignment(user_id=user.id, role_id=role.id, scope=GLOBAL.name, scope_object_id=None)
    session.add(assignment)
    await session.flush()
    assignment.soft_delete()
    session.add(assignment)
    await session.flush()

    await roles.delete_role(role.id, session)
    assert (await session.exec(select(Role).where(Role.id == role.id))).first() is None


async def _grant_at_role(
    session: AsyncSession, user_id: int, group_id: int, role_id: int, object_id: str, revoked: bool = False
) -> None:
    """Grant ``role_id`` to the user and to the group at ``role:<object_id>``, optionally soft-deleted."""
    user_grant = RoleAssignment(user_id=user_id, role_id=role_id, scope=ROLE.name, scope_object_id=object_id)
    group_grant = GroupRoleAssignment(group_id=group_id, role_id=role_id, scope=ROLE.name, scope_object_id=object_id)
    for grant in (user_grant, group_grant):
        if revoked:
            grant.soft_delete()
        session.add(grant)
    await session.flush()


async def _grants_at_role(session: AsyncSession, object_id: str) -> list[RoleAssignment | GroupRoleAssignment]:
    users = (
        await session.exec(
            select(RoleAssignment).where(RoleAssignment.scope == ROLE.name, RoleAssignment.scope_object_id == object_id)
        )
    ).all()
    groups = (
        await session.exec(
            select(GroupRoleAssignment).where(
                GroupRoleAssignment.scope == ROLE.name, GroupRoleAssignment.scope_object_id == object_id
            )
        )
    ).all()
    return [*users, *groups]


async def test_delete_role_removes_grants_scoped_to_it(session: AsyncSession) -> None:
    target = await roles.create_role("target", None, session)
    manager = await roles.create_role("manager", None, session)
    user = await make_user(session, "alice")
    group = await make_group(session, "staff")
    assert target.id is not None and manager.id is not None and user.id is not None and group.id is not None
    await _grant_at_role(session, user.id, group.id, manager.id, str(target.id))
    await _grant_at_role(session, user.id, group.id, manager.id, str(target.id), revoked=True)
    await roles.delete_role(target.id, session)
    assert await _grants_at_role(session, str(target.id)) == []
    assert (await session.exec(select(Role).where(Role.id == manager.id))).first() is not None


async def test_delete_role_keeps_grants_scoped_to_other_roles(session: AsyncSession) -> None:
    target = await roles.create_role("target", None, session)
    manager = await roles.create_role("manager", None, session)
    user = await make_user(session, "alice")
    group = await make_group(session, "staff")
    assert target.id is not None and manager.id is not None and user.id is not None and group.id is not None
    other_object_id = f"{target.id}7"
    await _grant_at_role(session, user.id, group.id, manager.id, str(target.id))
    await _grant_at_role(session, user.id, group.id, manager.id, other_object_id)
    await roles.delete_role(target.id, session)
    kept = await _grants_at_role(session, other_object_id)
    assert len(kept) == 2
    assert all(not grant.is_deleted for grant in kept)


async def test_set_role_permissions_adds_and_removes_to_match(session: AsyncSession) -> None:
    role = await roles.create_role("grader", None, session)
    assert role.id is not None
    await roles.set_role_permissions(role.id, ["assignment.grade"], session)

    await roles.set_role_permissions(role.id, ["role.read", "role.update"], session)

    assert sorted(await roles.get_role_permissions(role.id, session)) == ["role.read", "role.update"]


async def test_set_role_permissions_to_nothing_removes_every_grant(session: AsyncSession) -> None:
    role = await roles.create_role("grader", None, session)
    assert role.id is not None
    await roles.set_role_permissions(role.id, ["assignment.grade"], session)

    await roles.set_role_permissions(role.id, [], session)

    assert await roles.get_role_permissions(role.id, session) == []


async def test_set_role_permissions_returns_the_role(session: AsyncSession) -> None:
    role = await roles.create_role("grader", None, session)
    assert role.id is not None
    returned = await roles.set_role_permissions(role.id, ["assignment.grade"], session)
    assert (returned.id, returned.name) == (role.id, "grader")


async def test_set_role_permissions_with_an_unknown_permission_changes_nothing(session: AsyncSession) -> None:
    role = await roles.create_role("grader", None, session)
    assert role.id is not None
    await roles.set_role_permissions(role.id, ["assignment.grade"], session)

    with pytest.raises(PermissionNotFound):
        await roles.set_role_permissions(role.id, ["role.read", "bogus.unregistered"], session)

    assert await roles.get_role_permissions(role.id, session) == ["assignment.grade"]


async def test_set_role_permissions_keeps_an_undeclared_permission_still_listed(session: AsyncSession) -> None:
    role = await roles.create_role("grader", None, session)
    assert role.id is not None
    session.add(RolePermission(role_id=role.id, permission="retired.permission"))
    await session.commit()

    await roles.set_role_permissions(role.id, ["retired.permission", "role.read"], session)

    assert sorted(await roles.get_role_permissions(role.id, session)) == ["retired.permission", "role.read"]


async def test_set_role_permissions_removes_an_undeclared_permission_left_out(session: AsyncSession) -> None:
    role = await roles.create_role("grader", None, session)
    assert role.id is not None
    session.add(RolePermission(role_id=role.id, permission="retired.permission"))
    await session.commit()

    await roles.set_role_permissions(role.id, ["role.read"], session)

    assert await roles.get_role_permissions(role.id, session) == ["role.read"]


async def test_set_role_permissions_missing_role_raises(session: AsyncSession) -> None:
    with pytest.raises(RoleNotFound):
        await roles.set_role_permissions(999, ["assignment.grade"], session)


def test_available_permissions_includes_registered() -> None:
    assert "assignment.grade" in roles.available_permissions()


async def test_get_permissions_for_roles_groups_by_role(session: AsyncSession) -> None:
    role_a = await roles.create_role("role_a", None, session)
    role_b = await roles.create_role("role_b", None, session)
    assert role_a.id is not None and role_b.id is not None
    session.add(RolePermission(role_id=role_a.id, permission="assignment.grade"))
    session.add(RolePermission(role_id=role_a.id, permission="assignment.view"))
    session.add(RolePermission(role_id=role_b.id, permission="course.edit"))
    await session.flush()
    result = await roles.get_permissions_for_roles([role_a.id, role_b.id], session)
    assert sorted(result[role_a.id]) == ["assignment.grade", "assignment.view"]
    assert result[role_b.id] == ["course.edit"]


async def test_get_permissions_for_roles_includes_roles_without_grants(session: AsyncSession) -> None:
    role = await roles.create_role("empty", None, session)
    assert role.id is not None
    result = await roles.get_permissions_for_roles([role.id], session)
    assert result[role.id] == []


async def test_get_permissions_for_roles_empty_input_returns_empty_map(session: AsyncSession) -> None:
    assert await roles.get_permissions_for_roles([], session) == {}


async def test_create_role_with_permissions_grants_them(session: AsyncSession) -> None:
    role = await roles.create_role("grader", None, session, permissions=["role.read", "assignment.grade"])
    assert role.id is not None
    assert sorted(await roles.get_role_permissions(role.id, session)) == ["assignment.grade", "role.read"]


async def test_create_role_grants_a_permission_listed_twice_once(session: AsyncSession) -> None:
    role = await roles.create_role("grader", None, session, permissions=["role.read", "role.read"])
    assert role.id is not None
    assert await roles.get_role_permissions(role.id, session) == ["role.read"]


async def test_create_role_with_an_unknown_permission_creates_nothing(
    session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    with pytest.raises(PermissionNotFound):
        await roles.create_role("grader", None, session, permissions=["role.read", "bogus.unregistered"])

    assert (await session.exec(select(Role).where(Role.name == "grader"))).first() is None
    assert await audit_events() == []


async def test_create_role_is_not_builtin(session: AsyncSession) -> None:
    role = await roles.create_role("grader", None, session)
    assert role.is_builtin is False


async def test_delete_role_refuses_builtin_role(session: AsyncSession, audit_events: AuditEventsFetcher) -> None:
    role = await roles.create_role("admin", None, session)
    user = await make_user(session, "alice")
    assert role.id is not None and user.id is not None
    role.is_builtin = True
    session.add(RoleAssignment(user_id=user.id, role_id=role.id, scope=GLOBAL.name, scope_object_id=None))
    await session.flush()
    events_before = len(await audit_events())
    with pytest.raises(RoleIsBuiltin):
        await roles.delete_role(role.id, session)
    assert len(await audit_events()) == events_before
    assert await session.get(Role, role.id) is not None
    assignments = (await session.exec(select(RoleAssignment).where(RoleAssignment.role_id == role.id))).all()
    assert len(assignments) == 1


async def _make_builtin_role(session: AsyncSession) -> Role:
    """Create a built-in ``admin`` role that holds ``assignment.grade``."""
    role = await roles.create_role("admin", "Ships with Sparkth", session)
    assert role.id is not None
    await roles.set_role_permissions(role.id, ["assignment.grade"], session)
    role.is_builtin = True
    session.add(role)
    await session.commit()
    return role


_BUILTIN_ROLE_CHANGES: dict[str, Callable[[int, AsyncSession], Awaitable[object]]] = {
    "rename": lambda role_id, session: roles.update_role(role_id, "renamed", None, session),
    "same_name": lambda role_id, session: roles.update_role(role_id, "admin", None, session),
    "describe": lambda role_id, session: roles.update_role(role_id, None, "Changed", session),
    "set": lambda role_id, session: roles.set_role_permissions(role_id, ["role.read"], session),
    "set_unchanged": lambda role_id, session: roles.set_role_permissions(role_id, ["assignment.grade"], session),
    "delete": lambda role_id, session: roles.delete_role(role_id, session),
}


@pytest.mark.parametrize("change", _BUILTIN_ROLE_CHANGES.values(), ids=_BUILTIN_ROLE_CHANGES.keys())
async def test_changing_a_builtin_role_is_refused(
    change: Callable[[int, AsyncSession], Awaitable[object]],
    session: AsyncSession,
    audit_events: AuditEventsFetcher,
) -> None:
    role = await _make_builtin_role(session)
    assert role.id is not None
    events_before = len(await audit_events())
    with pytest.raises(RoleIsBuiltin):
        await change(role.id, session)
    assert len(await audit_events()) == events_before
    await session.refresh(role)
    assert (role.name, role.description) == ("admin", "Ships with Sparkth")
    assert await roles.get_role_permissions(role.id, session) == ["assignment.grade"]


async def test_a_builtin_role_can_still_be_assigned_and_revoked(session: AsyncSession) -> None:
    role = await _make_builtin_role(session)
    user = await make_user(session, "alice")
    group = await make_group(session, "staff")
    assert user.id is not None and group.id is not None
    await assign_role(user.id, "admin", GLOBAL, None, session)
    group_assignment = await assign_role_to_group(group.id, "admin", GLOBAL, None, session)
    assert await has_role(user, "admin", GLOBAL, None, session) is True
    assert group_assignment.role_id == role.id
    await revoke_role(user.id, "admin", GLOBAL, None, session)
    await revoke_role_from_group(group.id, "admin", GLOBAL, None, session)
    assert await has_role(user, "admin", GLOBAL, None, session) is False
    await session.refresh(group_assignment)
    assert group_assignment.is_deleted is True


async def test_get_role_assignee_counts_counts_each_person_and_group_once(session: AsyncSession) -> None:
    role = await roles.create_role("grader", None, session)
    alice = await make_user(session, "alice")
    bob = await make_user(session, "bob")
    staff = await make_group(session, "staff")
    assert role.id is not None and staff.id is not None
    await add_role_assignment(session, alice, role, GLOBAL.name, None)
    await add_role_assignment(session, alice, role, ROLE.name, "7")
    await add_role_assignment(session, bob, role, GLOBAL.name, None)
    session.add(GroupRoleAssignment(group_id=staff.id, role_id=role.id, scope=GLOBAL.name, scope_object_id=None))
    session.add(GroupRoleAssignment(group_id=staff.id, role_id=role.id, scope=ROLE.name, scope_object_id="7"))
    await session.flush()

    counts = await roles.get_role_assignee_counts([role.id], session)

    assert counts == {role.id: RoleAssigneeCounts(user_count=2, group_count=1)}


async def test_get_role_assignee_counts_ignores_revoked_assignments(session: AsyncSession) -> None:
    role = await roles.create_role("grader", None, session)
    alice = await make_user(session, "alice")
    alumni = await make_group(session, "alumni")
    assert role.id is not None and alumni.id is not None
    revoked = await add_role_assignment(session, alice, role, GLOBAL.name, None)
    revoked.soft_delete()
    revoked_group = GroupRoleAssignment(group_id=alumni.id, role_id=role.id, scope=GLOBAL.name, scope_object_id=None)
    revoked_group.soft_delete()
    session.add_all([revoked, revoked_group])
    await session.flush()

    counts = await roles.get_role_assignee_counts([role.id], session)

    assert counts == {role.id: RoleAssigneeCounts(user_count=0, group_count=0)}


async def test_get_role_assignee_counts_leaves_out_people_who_hold_it_only_through_a_group(
    session: AsyncSession,
) -> None:
    role = await roles.create_role("grader", None, session)
    alice = await make_user(session, "alice")
    assert role.id is not None
    await assign_through_group(session, alice, role, GLOBAL.name, None)

    counts = await roles.get_role_assignee_counts([role.id], session)

    assert counts == {role.id: RoleAssigneeCounts(user_count=0, group_count=1)}


async def test_get_role_assignee_counts_includes_roles_nobody_holds(session: AsyncSession) -> None:
    held = await roles.create_role("grader", None, session)
    unheld = await roles.create_role("viewer", None, session)
    alice = await make_user(session, "alice")
    assert held.id is not None and unheld.id is not None
    await add_role_assignment(session, alice, held, GLOBAL.name, None)

    counts = await roles.get_role_assignee_counts([held.id, unheld.id], session)

    assert counts == {
        held.id: RoleAssigneeCounts(user_count=1, group_count=0),
        unheld.id: RoleAssigneeCounts(user_count=0, group_count=0),
    }


async def test_get_role_assignee_counts_empty_input_returns_empty_map(session: AsyncSession) -> None:
    assert await roles.get_role_assignee_counts([], session) == {}


def test_get_role_risks_collects_each_risk_once_in_a_fixed_order() -> None:
    assert roles.get_role_risks(["audit.read", "role.delete", "group.delete", "role.update", "role.read"]) == [
        PermissionRisk.DELEGATES_ACCESS,
        PermissionRisk.PRIVATE_DATA,
        PermissionRisk.DELETES,
    ]


def test_get_role_risks_is_empty_for_permissions_without_risk() -> None:
    assert roles.get_role_risks(["permission.read", "analytics.read"]) == []


def test_get_role_risks_skips_a_permission_no_longer_declared() -> None:
    assert roles.get_role_risks(["no.such.permission", "role.delete"]) == [PermissionRisk.DELETES]
