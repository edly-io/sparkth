"""Engine tests: can()/has_role()/get_granted_scope_object_ids() resolving a user's own grants
and grants made to groups the user belongs to. Authored with LLM (Claude) assistance."""

from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User
from sparkth.core.permissions.models import (
    Group,
    GroupMembership,
    GroupRoleAssignment,
    Role,
    RoleAssignment,
    RolePermission,
)
from sparkth.lib.permissions import EMAIL_WHITELIST_READ, Permission, can, get_granted_scope_object_ids, has_role
from sparkth.lib.permissions.scopes import GLOBAL, GROUP, WHITELIST


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


async def make_group_grant(
    session: AsyncSession,
    user: User,
    role: Role,
    scope: str,
    scope_object_id: str | None,
) -> tuple[GroupMembership, GroupRoleAssignment]:
    """Create a group, add user as member, grant role to the group at the scope."""
    group = Group(name=f"grp-{user.username}-{role.name}-{scope}")
    session.add(group)
    await session.flush()
    assert group.id is not None and user.id is not None and role.id is not None
    membership = GroupMembership(user_id=user.id, group_id=group.id)
    assignment = GroupRoleAssignment(group_id=group.id, role_id=role.id, scope=scope, scope_object_id=scope_object_id)
    session.add(membership)
    session.add(assignment)
    await session.flush()
    return membership, assignment


async def test_can_allows_via_group_grant(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    role = await make_role(session, "grader", ["assignment.grade"])
    await make_group_grant(session, user, role, GLOBAL.name, None)
    assert await can(user, Permission("assignment.grade"), GLOBAL, None, session) is True


async def test_can_denies_non_member(session: AsyncSession) -> None:
    member = await make_user(session, "alice")
    outsider = await make_user(session, "bob")
    role = await make_role(session, "grader", ["assignment.grade"])
    await make_group_grant(session, member, role, GLOBAL.name, None)
    assert await can(outsider, Permission("assignment.grade"), GLOBAL, None, session) is False


async def test_group_grant_cascades_from_global_to_whitelist(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    role = await make_role(session, "admin", ["email.whitelist.read"])
    await make_group_grant(session, user, role, GLOBAL.name, None)
    assert await can(user, EMAIL_WHITELIST_READ, WHITELIST, None, session) is True


async def test_group_grant_at_child_does_not_satisfy_parent_check(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    role = await make_role(session, "wl", ["email.whitelist.read"])
    await make_group_grant(session, user, role, WHITELIST.name, None)
    assert await can(user, EMAIL_WHITELIST_READ, GLOBAL, None, session) is False


async def test_soft_deleted_membership_drops_the_grant(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    role = await make_role(session, "grader", ["assignment.grade"])
    membership, _ = await make_group_grant(session, user, role, GLOBAL.name, None)
    membership.soft_delete()
    await session.flush()
    assert await can(user, Permission("assignment.grade"), GLOBAL, None, session) is False


async def test_soft_deleted_group_assignment_drops_the_grant(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    role = await make_role(session, "grader", ["assignment.grade"])
    _, assignment = await make_group_grant(session, user, role, GLOBAL.name, None)
    assignment.soft_delete()
    await session.flush()
    assert await can(user, Permission("assignment.grade"), GLOBAL, None, session) is False


async def test_has_role_true_via_group_grant(session: AsyncSession) -> None:
    # api/v1/user/routes.py derives is_admin from has_role, so admin-via-group must count.
    user = await make_user(session, "alice")
    role = await make_role(session, "admin", [])
    await make_group_grant(session, user, role, GLOBAL.name, None)
    assert await has_role(user, "admin", GLOBAL, None, session) is True


async def test_has_role_via_group_is_scope_specific(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    role = await make_role(session, "grader", [])
    await make_group_grant(session, user, role, "course", "1")
    assert await has_role(user, "grader", GLOBAL, None, session) is False


async def assign_directly(
    session: AsyncSession, user: User, role: Role, scope: str, scope_object_id: str | None
) -> RoleAssignment:
    assert user.id is not None and role.id is not None
    assignment = RoleAssignment(user_id=user.id, role_id=role.id, scope=scope, scope_object_id=scope_object_id)
    session.add(assignment)
    await session.flush()
    return assignment


async def test_granted_scope_object_ids_from_direct_assignments(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    reader = await make_role(session, "reader", ["group.read"])
    other = await make_role(session, "other", ["group.update"])
    await assign_directly(session, user, reader, GROUP.name, "3")
    await assign_directly(session, user, reader, GROUP.name, "9")
    await assign_directly(session, user, other, GROUP.name, "4")
    assert await get_granted_scope_object_ids(user, Permission("group.read"), GROUP, session) == {"3", "9"}


async def test_granted_scope_object_ids_via_group(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    reader = await make_role(session, "reader", ["group.read"])
    await make_group_grant(session, user, reader, GROUP.name, "5")
    assert await get_granted_scope_object_ids(user, Permission("group.read"), GROUP, session) == {"5"}


async def test_granted_scope_object_ids_skips_revoked_and_other_scopes(session: AsyncSession) -> None:
    # Only active grants at exactly the asked scope count: a revoked one, an ancestor (global)
    # grant, and a grant at another scope kind all contribute nothing.
    user = await make_user(session, "alice")
    reader = await make_role(session, "reader", ["group.read"])
    revoked = await assign_directly(session, user, reader, GROUP.name, "6")
    revoked.soft_delete()
    await assign_directly(session, user, reader, GLOBAL.name, None)
    await assign_directly(session, user, reader, "course", "7")
    await session.flush()
    assert await get_granted_scope_object_ids(user, Permission("group.read"), GROUP, session) == set()


async def test_granted_scope_object_ids_skips_left_group(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    reader = await make_role(session, "reader", ["group.read"])
    membership, _ = await make_group_grant(session, user, reader, GROUP.name, "5")
    membership.soft_delete()
    await session.flush()
    assert await get_granted_scope_object_ids(user, Permission("group.read"), GROUP, session) == set()
