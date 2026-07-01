"""Scoped-RBAC permission functions.

The public surface is re-exported from ``app.lib.permissions``
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ColumnElement
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.permissions.exceptions import RoleNotFound
from app.core.permissions.models import Role, RoleAssignment, RolePermission
from app.core.permissions.scopes import PermissionScope
from app.models.user import User

if TYPE_CHECKING:
    # Annotation-only: importing Permission at runtime would cycle — the package __init__
    # imports dependency.py, which imports can() from this module before __init__ finishes.
    from app.core.permissions import Permission


def _active_assignment_at_scope(
    user_id: int | None,
    permission_scope: PermissionScope,
    scope_object_id: str | None,
) -> tuple[ColumnElement[bool], ...]:
    """WHERE clauses selecting a user's active role assignments at one permission scope.

    Shared by the read-side checks (``can`` and ``has_role``) so they resolve a scope
    identically — the single place to change when scope hierarchy lands, which keeps the
    two from diverging.

    TODO(scope hierarchy): matches the exact (scope, scope_object_id) only — a role granted
    at a parent scope does not yet cascade to descendants (see PermissionScope.get_parents()).
    Cascading is the end goal and lands here.

    The write operations (``assign_role``, ``revoke_role``) deliberately target the exact
    assignment row and must NOT use this — they never cascade to parent scopes.
    """
    return (
        col(RoleAssignment.user_id) == user_id,
        col(RoleAssignment.is_deleted) == False,
        col(RoleAssignment.scope) == permission_scope.name,
        col(RoleAssignment.scope_object_id) == scope_object_id,
    )


async def _find_active_assignment(
    user_id: int,
    role_id: int,
    permission_scope: PermissionScope,
    scope_object_id: str | None,
    session: AsyncSession,
) -> RoleAssignment | None:
    """Return the user's active assignment of role_id at the exact scope, or None."""
    statement = (
        select(RoleAssignment)
        .where(
            RoleAssignment.user_id == user_id,
            RoleAssignment.role_id == role_id,
            RoleAssignment.scope == permission_scope.name,
            RoleAssignment.scope_object_id == scope_object_id,
            RoleAssignment.is_deleted == False,
        )
        .limit(1)
    )
    return (await session.exec(statement)).first()


async def can(
    user: User,
    permission: Permission,
    permission_scope: PermissionScope,
    scope_object_id: str | None,
    session: AsyncSession,
) -> bool:
    """Return whether user holds permission at the given permission scope."""
    statement = (
        select(RolePermission.permission)
        .join(RoleAssignment, col(RoleAssignment.role_id) == col(RolePermission.role_id))
        .where(
            *_active_assignment_at_scope(user.id, permission_scope, scope_object_id),
            RolePermission.permission == permission.name,
        )
        .limit(1)
    )
    result = await session.exec(statement)
    return result.first() is not None


async def has_role(
    user: User,
    role_name: str,
    permission_scope: PermissionScope,
    scope_object_id: str | None,
    session: AsyncSession,
) -> bool:
    """Return whether user holds an active assignment of role_name at the given permission scope."""
    statement = (
        select(RoleAssignment.id)
        .join(Role, col(Role.id) == col(RoleAssignment.role_id))
        .where(
            *_active_assignment_at_scope(user.id, permission_scope, scope_object_id),
            Role.name == role_name,
        )
        .limit(1)
    )
    result = await session.exec(statement)
    return result.first() is not None


async def assign_role(
    user_id: int,
    role_name: str,
    permission_scope: PermissionScope,
    scope_object_id: str | None,
    session: AsyncSession,
) -> RoleAssignment:
    """Return the active assignment of role_name to user_id at the given permission scope, creating it if absent.

    Idempotent and race-safe: if a concurrent assign inserts the same (user, role, scope)
    between the existence check and our insert, the unique index rejects ours; we recover by
    re-querying and returning the winner instead of surfacing the IntegrityError.

    Raises RoleNotFound if the role does not exist.
    """
    role = (await session.exec(select(Role).where(Role.name == role_name))).one_or_none()
    if role is None or role.id is None:
        raise RoleNotFound(role_name)
    existing = await _find_active_assignment(user_id, role.id, permission_scope, scope_object_id, session)
    if existing is not None:
        return existing
    try:
        # Insert inside a savepoint so a unique-index violation rolls back cleanly without
        # poisoning the surrounding transaction.
        async with session.begin_nested():
            assignment = RoleAssignment(
                user_id=user_id, role_id=role.id, scope=permission_scope.name, scope_object_id=scope_object_id
            )
            session.add(assignment)
            await session.flush()
        return assignment
    except IntegrityError:
        # A concurrent assign_role inserted the same (user, role, scope) after our check, so
        # the unique index rejected ours. Re-query and return that winner to stay idempotent;
        # if it's somehow still not visible, re-raise.
        winner = await _find_active_assignment(user_id, role.id, permission_scope, scope_object_id, session)
        if winner is None:
            raise
        return winner


async def revoke_role(
    user_id: int,
    role_name: str,
    permission_scope: PermissionScope,
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
            RoleAssignment.scope == permission_scope.name,
            RoleAssignment.scope_object_id == scope_object_id,
            RoleAssignment.is_deleted == False,
        )
    )
    assignments = (await session.exec(statement)).all()
    for assignment in assignments:
        # Already tracked by the session (they came from this query), so mutating them marks
        # them dirty — no session.add needed.
        assignment.soft_delete()
    await session.flush()
