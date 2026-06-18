import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.permissions import Role, RoleAssignment, RolePermission
from app.models.user import User
from app.permissions.constants import SCOPE_GLOBAL
from app.permissions.exceptions import RoleNotFound
from app.permissions.service import PermissionService


def test_scope_global_constant() -> None:
    assert SCOPE_GLOBAL == "global"


def test_role_not_found_carries_name() -> None:
    exc = RoleNotFound("teacher")
    assert exc.role_name == "teacher"
    assert "teacher" in str(exc)


async def test_role_assignment_defaults_to_global_scope(session: AsyncSession) -> None:
    role = Role(name="grader")
    session.add(role)
    await session.flush()
    assert role.id is not None

    assignment = RoleAssignment(user_id=1, role_id=role.id)
    session.add(assignment)
    await session.flush()

    assert assignment.id is not None
    assert assignment.scope_type == SCOPE_GLOBAL
    assert assignment.scope_id is None
    assert assignment.is_deleted is False


async def test_role_permission_round_trips(session: AsyncSession) -> None:
    role = Role(name="grader")
    session.add(role)
    await session.flush()
    assert role.id is not None

    session.add(RolePermission(role_id=role.id, permission="assignment.grade"))
    await session.flush()


async def make_user(session: AsyncSession, username: str, is_superuser: bool = False) -> User:
    user = User(
        name="T",
        username=username,
        email=f"{username}@example.com",
        hashed_password="x",
        is_superuser=is_superuser,
    )
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


async def test_can_denies_without_assignment(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    assert await PermissionService(session).can(user, "assignment.grade") is False


async def test_can_allows_with_assigned_role(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    role = await make_role(session, "grader", ["assignment.grade"])
    assert user.id is not None and role.id is not None
    session.add(RoleAssignment(user_id=user.id, role_id=role.id))
    await session.flush()
    assert await PermissionService(session).can(user, "assignment.grade") is True


async def test_can_superuser_fast_path(session: AsyncSession) -> None:
    user = await make_user(session, "root", is_superuser=True)
    assert await PermissionService(session).can(user, "anything.at.all") is True


async def test_can_denies_permission_at_other_scope(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    role = await make_role(session, "grader", ["assignment.grade"])
    assert user.id is not None and role.id is not None
    session.add(RoleAssignment(user_id=user.id, role_id=role.id, scope_type="course", scope_id="1"))
    await session.flush()
    assert await PermissionService(session).can(user, "assignment.grade") is False


async def test_assign_role_creates_assignment(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    assert user.id is not None
    await make_role(session, "grader", ["assignment.grade"])
    service = PermissionService(session)
    assignment = await service.assign_role(user.id, "grader")
    assert assignment.id is not None
    assert await service.can(user, "assignment.grade") is True


async def test_assign_role_unknown_role_raises(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    assert user.id is not None
    with pytest.raises(RoleNotFound):
        await PermissionService(session).assign_role(user.id, "nope")


async def test_revoke_role_revokes_access(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    assert user.id is not None
    await make_role(session, "grader", ["assignment.grade"])
    service = PermissionService(session)
    await service.assign_role(user.id, "grader")
    await service.revoke_role(user.id, "grader")
    assert await service.can(user, "assignment.grade") is False


async def test_revoke_role_noop_when_no_assignment(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    assert user.id is not None
    await make_role(session, "grader", ["assignment.grade"])
    await PermissionService(session).revoke_role(user.id, "grader")
