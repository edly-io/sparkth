"""Engine tests: can()/has_role() resolving grants made to groups the user belongs to.
Authored with LLM (Claude) assistance."""

from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.permissions import EMAIL_WHITELIST_READ, Permission, can, has_role
from sparkth.lib.permissions.scopes import GLOBAL, WHITELIST, PermissionScope
from sparkth.lib.testing import assign_through_group, make_role, make_user


async def test_can_allows_via_group_grant(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    role = await make_role(session, "grader", ["assignment.grade"])
    await assign_through_group(session, user, role, GLOBAL.name, None)
    assert await can(user, Permission("assignment.grade"), GLOBAL, None, session) is True


async def test_can_denies_non_member(session: AsyncSession) -> None:
    member = await make_user(session, "alice")
    outsider = await make_user(session, "bob")
    role = await make_role(session, "grader", ["assignment.grade"])
    await assign_through_group(session, member, role, GLOBAL.name, None)
    assert await can(outsider, Permission("assignment.grade"), GLOBAL, None, session) is False


async def test_group_grant_cascades_from_global_to_whitelist(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    role = await make_role(session, "admin", ["email.whitelist.read"])
    await assign_through_group(session, user, role, GLOBAL.name, None)
    assert await can(user, EMAIL_WHITELIST_READ, WHITELIST, None, session) is True


async def test_group_grant_at_child_does_not_satisfy_parent_check(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    role = await make_role(session, "wl", ["email.whitelist.read"])
    await assign_through_group(session, user, role, WHITELIST.name, None)
    assert await can(user, EMAIL_WHITELIST_READ, GLOBAL, None, session) is False


async def test_soft_deleted_membership_drops_the_grant(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    role = await make_role(session, "grader", ["assignment.grade"])
    membership, _ = await assign_through_group(session, user, role, GLOBAL.name, None)
    membership.soft_delete()
    await session.flush()
    assert await can(user, Permission("assignment.grade"), GLOBAL, None, session) is False


async def test_soft_deleted_group_assignment_drops_the_grant(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    role = await make_role(session, "grader", ["assignment.grade"])
    _, assignment = await assign_through_group(session, user, role, GLOBAL.name, None)
    assignment.soft_delete()
    await session.flush()
    assert await can(user, Permission("assignment.grade"), GLOBAL, None, session) is False


async def test_has_role_true_via_group_grant(session: AsyncSession) -> None:
    # A role granted through a group counts as held, like a direct assignment.
    user = await make_user(session, "alice")
    role = await make_role(session, "admin", [])
    await assign_through_group(session, user, role, GLOBAL.name, None)
    assert await has_role(user, "admin", GLOBAL, None, session) is True


async def test_has_role_via_group_is_scope_specific(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    role = await make_role(session, "grader", [])
    await assign_through_group(session, user, role, "course", "1")
    assert await has_role(user, "grader", GLOBAL, None, session) is False


async def test_group_assignment_cascades_through_scope_path(session: AsyncSession) -> None:
    org = PermissionScope("org", parent=GLOBAL)
    course = PermissionScope("course", parent=org)
    user = await make_user(session, "alice")
    role = await make_role(session, "grader", ["assignment.grade"])
    await assign_through_group(session, user, role, "org", "5")
    permission = Permission("assignment.grade")
    assert await can(user, permission, course, "org:5/course:123", session) is True
    assert await can(user, permission, course, "org:6/course:123", session) is False
