"""Role grants: assigning and revoking roles for users, and removing the grants scoped to an object.

``assign_role`` and ``revoke_role`` change a user's role assignments, and
``delete_grants_at_object`` removes every user and group grant scoped to one object when that
object is deleted. Each active grant removed is recorded as a ``role.unassigned`` or
``group.role_revoked`` audit event in the caller's transaction, with the snapshot built by
``create_grant_audit_snapshot`` from the row's own scope strings.

None of these need the ``Permission`` class, so they live apart from the RBAC gate in
``sparkth.core.permissions``. The public surface is re-exported from ``sparkth.lib.permissions``.
"""

from sqlalchemy import ColumnElement, and_, delete
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.permissions.exceptions import RoleNotFound
from sparkth.core.permissions.models import GroupRoleAssignment, Role, RoleAssignment
from sparkth.core.permissions.scopes import PermissionScope
from sparkth.lib.audit import record_event
from sparkth.lib.audit.events import (
    AuditChange,
    AuditOutcome,
    AuditTarget,
    GroupRoleRevokedAuditEvent,
    RoleAssignedAuditEvent,
    RoleUnassignedAuditEvent,
)


def create_grant_audit_snapshot(role_name: str, scope_name: str, scope_object_id: str | None) -> dict[str, str | None]:
    """Audit snapshot of a role grant at a scope, shared by user and group assignments.

    Takes the scope's stored name, so a grant whose scope kind is no longer registered can
    still be snapshotted from its own row.
    """
    return {"role": role_name, "scope": scope_name, "scope_object_id": scope_object_id}


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

    Creating the assignment records ``role.assigned`` in the caller's transaction; returning
    an existing (or concurrently inserted) assignment records nothing.

    Raises RoleNotFound if the role does not exist. Raises InvalidScopeObjectId if the
    (permission_scope, scope_object_id) pairing is invalid (see PermissionScope.validate_object_id).
    """
    permission_scope.validate_object_id(scope_object_id)
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
    except IntegrityError:
        # A concurrent assign_role inserted the same (user, role, scope) after our check, so
        # the unique index rejected ours. Re-query and return that winner to stay idempotent;
        # if it's somehow still not visible, re-raise.
        winner = await _find_active_assignment(user_id, role.id, permission_scope, scope_object_id, session)
        if winner is None:
            raise
        return winner
    await record_event(
        session,
        RoleAssignedAuditEvent(
            outcome=AuditOutcome.SUCCESS,
            target=AuditTarget(type="user", id=str(user_id)),
            change=AuditChange(new=create_grant_audit_snapshot(role_name, permission_scope.name, scope_object_id)),
        ),
    )
    return assignment


async def revoke_role(
    user_id: int,
    role_name: str,
    permission_scope: PermissionScope,
    scope_object_id: str | None,
    session: AsyncSession,
) -> None:
    """Soft-delete all active assignments of role_name for user_id at the given permission scope.

    Revoking an active assignment records ``role.unassigned`` in the caller's transaction; a
    call that finds nothing active records nothing.
    """
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
    if assignments:
        await record_event(
            session,
            RoleUnassignedAuditEvent(
                outcome=AuditOutcome.SUCCESS,
                target=AuditTarget(type="user", id=str(user_id)),
                change=AuditChange(old=create_grant_audit_snapshot(role_name, permission_scope.name, scope_object_id)),
            ),
        )


async def record_active_user_grants_removed(match: ColumnElement[bool], session: AsyncSession) -> None:
    """Record ``role.unassigned`` for each active user assignment satisfying ``match``."""
    user_rows = await session.exec(
        select(RoleAssignment.user_id, Role.name, RoleAssignment.scope, RoleAssignment.scope_object_id)
        .join(Role, col(Role.id) == col(RoleAssignment.role_id))
        .where(match, RoleAssignment.is_deleted == False)
        .order_by(col(RoleAssignment.id))
    )
    for user_id, role_name, scope_name, object_id in user_rows.all():
        await record_event(
            session,
            RoleUnassignedAuditEvent(
                outcome=AuditOutcome.SUCCESS,
                target=AuditTarget(type="user", id=str(user_id)),
                change=AuditChange(old=create_grant_audit_snapshot(role_name, scope_name, object_id)),
            ),
        )


async def record_active_group_grants_removed(match: ColumnElement[bool], session: AsyncSession) -> None:
    """Record ``group.role_revoked`` for each active group assignment satisfying ``match``."""
    group_rows = await session.exec(
        select(GroupRoleAssignment.group_id, Role.name, GroupRoleAssignment.scope, GroupRoleAssignment.scope_object_id)
        .join(Role, col(Role.id) == col(GroupRoleAssignment.role_id))
        .where(match, GroupRoleAssignment.is_deleted == False)
        .order_by(col(GroupRoleAssignment.id))
    )
    for group_id, role_name, scope_name, object_id in group_rows.all():
        await record_event(
            session,
            GroupRoleRevokedAuditEvent(
                outcome=AuditOutcome.SUCCESS,
                target=AuditTarget(type="group", id=str(group_id)),
                change=AuditChange(old=create_grant_audit_snapshot(role_name, scope_name, object_id)),
            ),
        )


async def delete_grants_at_object(
    permission_scope: PermissionScope,
    scope_object_id: str,
    session: AsyncSession,
) -> None:
    """Delete every user and group grant scoped to one object, active and revoked.

    Each active grant is recorded first (``role.unassigned`` per user grant, then
    ``group.role_revoked`` per group grant), snapshotted from the row's own scope strings so a
    scope kind that is no longer registered still works; revoked rows record nothing.
    ``scope_object_id`` is matched exactly. Flushes in the caller's transaction, never commits.
    """
    user_match = and_(
        col(RoleAssignment.scope) == permission_scope.name, col(RoleAssignment.scope_object_id) == scope_object_id
    )
    group_match = and_(
        col(GroupRoleAssignment.scope) == permission_scope.name,
        col(GroupRoleAssignment.scope_object_id) == scope_object_id,
    )
    await record_active_user_grants_removed(user_match, session)
    await record_active_group_grants_removed(group_match, session)
    await session.exec(delete(RoleAssignment).where(user_match))
    await session.exec(delete(GroupRoleAssignment).where(group_match))
    await session.flush()
