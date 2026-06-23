"""Scoped-RBAC permission functions.

The public surface is re-exported from ``app.lib.permissions``
"""

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.permissions.exceptions import RoleNotFound
from app.core.permissions.models import Role, RoleAssignment, RolePermission
from app.models.user import User


async def can(
    user: User,
    permission: str,
    permission_scope: str,
    scope_object_id: str | None,
    session: AsyncSession,
) -> bool:
    """Return whether user holds permission at the given permission scope."""
    statement = (
        select(RolePermission.permission)
        .join(RoleAssignment, col(RoleAssignment.role_id) == col(RolePermission.role_id))
        .where(
            RoleAssignment.user_id == user.id,
            RoleAssignment.is_deleted == False,
            RoleAssignment.scope == permission_scope,
            RoleAssignment.scope_object_id == scope_object_id,
            RolePermission.permission == permission,
        )
        .limit(1)
    )
    result = await session.exec(statement)
    return result.first() is not None


async def assign_role(
    user_id: int,
    role_name: str,
    permission_scope: str,
    scope_object_id: str | None,
    session: AsyncSession,
) -> RoleAssignment:
    """Return the active assignment of role_name to user_id at the given permission scope, creating it if absent.

    Raises RoleNotFound if the role does not exist.
    """
    role = (await session.exec(select(Role).where(Role.name == role_name))).one_or_none()
    if role is None or role.id is None:
        raise RoleNotFound(role_name)
    existing = (
        await session.exec(
            select(RoleAssignment)
            .where(
                RoleAssignment.user_id == user_id,
                RoleAssignment.role_id == role.id,
                RoleAssignment.scope == permission_scope,
                RoleAssignment.scope_object_id == scope_object_id,
                RoleAssignment.is_deleted == False,
            )
            .limit(1)
        )
    ).first()
    if existing is not None:
        return existing
    assignment = RoleAssignment(
        user_id=user_id, role_id=role.id, scope=permission_scope, scope_object_id=scope_object_id
    )
    session.add(assignment)
    await session.flush()
    return assignment


async def revoke_role(
    user_id: int,
    role_name: str,
    permission_scope: str,
    scope_object_id: str | None,
    session: AsyncSession,
) -> None:
    """Soft-delete all active assignments of role_name for user_id at the given permission scope."""
    statement = (
        select(RoleAssignment)
        .join(Role, col(Role.id) == col(RoleAssignment.role_id))
        .where(
            RoleAssignment.user_id == user_id,
            Role.name == role_name,
            RoleAssignment.scope == permission_scope,
            RoleAssignment.scope_object_id == scope_object_id,
            RoleAssignment.is_deleted == False,
        )
    )
    assignments = (await session.exec(statement)).all()
    for assignment in assignments:
        assignment.soft_delete()
        session.add(assignment)
    await session.flush()
