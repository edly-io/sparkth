from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.permissions import Role, RoleAssignment, RolePermission
from app.permissions.constants import SCOPE_GLOBAL
from app.permissions.exceptions import RoleNotFound


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
