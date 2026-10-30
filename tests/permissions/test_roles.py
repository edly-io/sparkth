"""Tests for the role-CRUD engine functions (sparkth.core.permissions.roles)."""

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.permissions import PERMISSIONS, Permission, roles
from sparkth.core.permissions.exceptions import (
    PermissionNotFound,
    RoleAlreadyExists,
    RoleInUse,
    RoleNotDeletable,
    RoleNotFound,
)
from sparkth.core.permissions.models import GroupRoleAssignment, Role, RoleAssignment, RolePermission
from sparkth.lib.permissions.scopes import GLOBAL


@pytest.fixture(autouse=True)
def _register_test_permission(monkeypatch: pytest.MonkeyPatch) -> None:
    # add_role_permission validates against the registry, so register a known permission on the
    # PERMISSIONS hook for the duration of one test. monkeypatch restores the backing dict after
    # each test, so the permission never leaks into the shared vocabulary other tests see.
    monkeypatch.setitem(PERMISSIONS._items, "assignment.grade", Permission("assignment.grade"))


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
    result = await roles.list_roles(session)
    assert {r.name for r in result} == {"a", "b"}


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
    await roles.add_role_permission(role.id, "assignment.grade", session)
    await roles.delete_role(role.id, session)
    assert (await session.exec(select(Role).where(Role.id == role.id))).first() is None
    assert (await session.exec(select(RolePermission).where(RolePermission.role_id == role.id))).all() == []


async def test_delete_role_missing_raises(session: AsyncSession) -> None:
    with pytest.raises(RoleNotFound):
        await roles.delete_role(999, session)


async def test_delete_role_blocked_when_actively_assigned(session: AsyncSession) -> None:
    role = await roles.create_role("grader", None, session)
    assert role.id is not None
    session.add(RoleAssignment(user_id=1, role_id=role.id, scope=GLOBAL.name, scope_object_id=None))
    await session.flush()
    with pytest.raises(RoleInUse):
        await roles.delete_role(role.id, session)


async def test_delete_role_allowed_when_only_soft_deleted_assignment(session: AsyncSession) -> None:
    role = await roles.create_role("grader", None, session)
    assert role.id is not None
    assignment = RoleAssignment(user_id=1, role_id=role.id, scope=GLOBAL.name, scope_object_id=None)
    session.add(assignment)
    await session.flush()
    assignment.soft_delete()
    session.add(assignment)
    await session.flush()

    await roles.delete_role(role.id, session)
    assert (await session.exec(select(Role).where(Role.id == role.id))).first() is None


async def _grant_at_role(session: AsyncSession, role_id: int, object_id: str, revoked: bool = False) -> None:
    """Add a user and a group grant of ``role_id`` at ``role:<object_id>``, optionally soft-deleted."""
    user_grant = RoleAssignment(user_id=1, role_id=role_id, scope="role", scope_object_id=object_id)
    group_grant = GroupRoleAssignment(group_id=1, role_id=role_id, scope="role", scope_object_id=object_id)
    for grant in (user_grant, group_grant):
        if revoked:
            grant.soft_delete()
        session.add(grant)
    await session.flush()


async def _grants_at_role(session: AsyncSession, object_id: str) -> list[RoleAssignment | GroupRoleAssignment]:
    users = (
        await session.exec(
            select(RoleAssignment).where(RoleAssignment.scope == "role", RoleAssignment.scope_object_id == object_id)
        )
    ).all()
    groups = (
        await session.exec(
            select(GroupRoleAssignment).where(
                GroupRoleAssignment.scope == "role", GroupRoleAssignment.scope_object_id == object_id
            )
        )
    ).all()
    return [*users, *groups]


async def test_delete_role_removes_grants_scoped_to_it(session: AsyncSession) -> None:
    target = await roles.create_role("target", None, session)
    manager = await roles.create_role("manager", None, session)
    assert target.id is not None and manager.id is not None
    await _grant_at_role(session, manager.id, str(target.id))
    await _grant_at_role(session, manager.id, str(target.id), revoked=True)
    await roles.delete_role(target.id, session)
    assert await _grants_at_role(session, str(target.id)) == []
    assert (await session.exec(select(Role).where(Role.id == manager.id))).first() is not None


async def test_delete_role_keeps_grants_scoped_to_other_roles(session: AsyncSession) -> None:
    target = await roles.create_role("target", None, session)
    manager = await roles.create_role("manager", None, session)
    assert target.id is not None and manager.id is not None
    other_object_id = f"{target.id}7"
    await _grant_at_role(session, manager.id, str(target.id))
    await _grant_at_role(session, manager.id, other_object_id)
    await roles.delete_role(target.id, session)
    kept = await _grants_at_role(session, other_object_id)
    assert len(kept) == 2
    assert all(not grant.is_deleted for grant in kept)


async def test_new_role_does_not_inherit_grants_of_a_deleted_role_id(session: AsyncSession) -> None:
    manager = await roles.create_role("manager", None, session)
    target = await roles.create_role("target", None, session)
    assert target.id is not None and manager.id is not None
    target_id = target.id
    await _grant_at_role(session, manager.id, str(target_id))
    await roles.delete_role(target_id, session)
    new_role = await roles.create_role("newcomer", None, session)
    assert new_role.id == target_id
    active = [grant for grant in await _grants_at_role(session, str(target_id)) if not grant.is_deleted]
    assert active == []


async def test_add_role_permission_grants(session: AsyncSession) -> None:
    role = await roles.create_role("grader", None, session)
    assert role.id is not None
    await roles.add_role_permission(role.id, "assignment.grade", session)
    assert await roles.get_role_permissions(role.id, session) == ["assignment.grade"]


async def test_add_role_permission_unknown_permission_raises(session: AsyncSession) -> None:
    role = await roles.create_role("grader", None, session)
    assert role.id is not None
    with pytest.raises(PermissionNotFound):
        await roles.add_role_permission(role.id, "bogus.unregistered", session)


async def test_add_role_permission_missing_role_raises(session: AsyncSession) -> None:
    with pytest.raises(RoleNotFound):
        await roles.add_role_permission(999, "assignment.grade", session)


async def test_add_role_permission_is_idempotent(session: AsyncSession) -> None:
    role = await roles.create_role("grader", None, session)
    assert role.id is not None
    await roles.add_role_permission(role.id, "assignment.grade", session)
    # Granting the same permission again is a no-op, not an error.
    await roles.add_role_permission(role.id, "assignment.grade", session)
    assert await roles.get_role_permissions(role.id, session) == ["assignment.grade"]


async def test_remove_role_permission_revokes(session: AsyncSession) -> None:
    role = await roles.create_role("grader", None, session)
    assert role.id is not None
    await roles.add_role_permission(role.id, "assignment.grade", session)
    await roles.remove_role_permission(role.id, "assignment.grade", session)
    assert await roles.get_role_permissions(role.id, session) == []


async def test_remove_role_permission_is_idempotent(session: AsyncSession) -> None:
    role = await roles.create_role("grader", None, session)
    assert role.id is not None
    # Removing a grant the role doesn't have is a no-op (idempotent DELETE).
    await roles.remove_role_permission(role.id, "assignment.grade", session)
    assert await roles.get_role_permissions(role.id, session) == []


async def test_remove_role_permission_missing_role_raises(session: AsyncSession) -> None:
    with pytest.raises(RoleNotFound):
        await roles.remove_role_permission(999, "assignment.grade", session)


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


async def test_add_role_permission_returns_the_role(session: AsyncSession) -> None:
    role = await roles.create_role("grader", None, session)
    assert role.id is not None
    returned = await roles.add_role_permission(role.id, "assignment.grade", session)
    assert returned.id == role.id
    assert returned.name == "grader"


async def test_create_role_is_deletable(session: AsyncSession) -> None:
    role = await roles.create_role("grader", None, session)
    assert role.deletable is True


async def test_delete_role_refuses_non_deletable_role(session: AsyncSession) -> None:
    role = await roles.create_role("admin", None, session)
    assert role.id is not None
    role.deletable = False
    session.add(RoleAssignment(user_id=1, role_id=role.id, scope=GLOBAL.name, scope_object_id=None))
    await session.flush()
    with pytest.raises(RoleNotDeletable):
        await roles.delete_role(role.id, session)
    assert await session.get(Role, role.id) is not None
    assignments = (await session.exec(select(RoleAssignment).where(RoleAssignment.role_id == role.id))).all()
    assert len(assignments) == 1
