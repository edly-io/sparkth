"""Group CRUD, membership, and group-role-grant management (issue #519).

Module-level async functions mirroring the role engine. The CRUD functions commit
(like ``roles.py``); the membership and assignment functions only flush (like
``assign_role`` / ``revoke_role``), so their callers own the transaction boundary.
Every change is recorded as a ``group.*`` audit event in that same transaction; an
idempotent call that changes nothing records nothing.
Authored with LLM (Claude) assistance.
"""

from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.permissions import _create_grant_audit_snapshot
from sparkth.core.permissions.exceptions import (
    GroupAlreadyExists,
    GroupInUse,
    GroupNotFound,
    RoleNotFound,
)
from sparkth.core.permissions.models import Group, GroupMembership, GroupRoleAssignment, Role
from sparkth.core.permissions.scopes import PermissionScope
from sparkth.lib.audit import record_event
from sparkth.lib.audit.events import (
    AuditChange,
    AuditOutcome,
    AuditTarget,
    GroupCreatedAuditEvent,
    GroupDeletedAuditEvent,
    GroupMemberAddedAuditEvent,
    GroupMemberRemovedAuditEvent,
    GroupRoleAssignedAuditEvent,
    GroupRoleRevokedAuditEvent,
    GroupUpdatedAuditEvent,
)


def _target(group_id: int | None) -> AuditTarget:
    return AuditTarget(type="group", id=str(group_id))


def _create_audit_snapshot(group: Group) -> dict[str, str | None]:
    return {"name": group.name, "description": group.description}


async def create_group(name: str, description: str | None, session: AsyncSession) -> Group:
    """Create and return a group, recording ``group.created``.

    Raises GroupAlreadyExists if the name is already taken. Race-safe: when a concurrent
    create takes the name between the pre-check and the insert, the unique-index
    IntegrityError is translated into GroupAlreadyExists (the name index is the only
    constraint on user_group that can fire here). The membership and assignment functions
    below use a savepoint for the same job because they only flush; the CRUD functions own
    the transaction, so rolling it back is enough.
    """
    if (await session.exec(select(Group).where(Group.name == name))).first() is not None:
        raise GroupAlreadyExists(name)
    group = Group(name=name, description=description)
    session.add(group)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise GroupAlreadyExists(name)
    await record_event(
        session,
        GroupCreatedAuditEvent(
            outcome=AuditOutcome.SUCCESS,
            target=_target(group.id),
            change=AuditChange(new=_create_audit_snapshot(group)),
        ),
    )
    await session.commit()
    await session.refresh(group)
    return group


async def list_groups(session: AsyncSession) -> list[Group]:
    """Return every group, oldest first."""
    return list((await session.exec(select(Group).order_by(col(Group.id)))).all())


async def get_group(group_id: int, session: AsyncSession) -> Group:
    """Return the group with group_id, or raise GroupNotFound."""
    group = await session.get(Group, group_id)
    if group is None:
        raise GroupNotFound(str(group_id))
    return group


async def get_group_by_name(name: str, session: AsyncSession) -> Group:
    """Return the group named ``name``, or raise GroupNotFound. The CLI resolves names with this."""
    group = (await session.exec(select(Group).where(Group.name == name))).first()
    if group is None:
        raise GroupNotFound(name)
    return group


async def update_group(group_id: int, name: str | None, description: str | None, session: AsyncSession) -> Group:
    """Update a group's name and/or description, record ``group.updated``, and return it.

    A None argument leaves that field unchanged; an update that changes nothing records
    nothing. Raises GroupNotFound if the group is missing, or GroupAlreadyExists if name
    collides with another group (race-safe, like create_group).
    """
    group = await get_group(group_id, session)
    before = _create_audit_snapshot(group)
    if name is not None and name != group.name:
        if (await session.exec(select(Group).where(Group.name == name))).first() is not None:
            raise GroupAlreadyExists(name)
        group.name = name
    if description is not None:
        group.description = description
    if _create_audit_snapshot(group) == before:
        return group
    group.update_timestamp()
    session.add(group)
    try:
        await session.flush()
    except IntegrityError:
        # A concurrent create/rename took the name between the pre-check and the flush;
        # only the name unique index can fire here (translated like create_group).
        await session.rollback()
        if name is None:
            raise
        raise GroupAlreadyExists(name)
    await record_event(
        session,
        GroupUpdatedAuditEvent(
            outcome=AuditOutcome.SUCCESS,
            target=_target(group.id),
            change=AuditChange(old=before, new=_create_audit_snapshot(group)),
        ),
    )
    await session.commit()
    await session.refresh(group)
    return group


async def delete_group(group_id: int, session: AsyncSession) -> None:
    """Delete a group together with its membership and assignment history, recording ``group.deleted``.

    Raises GroupNotFound if the group is missing, or GroupInUse if it still has an active
    role assignment. Members alone do not block; membership rows (active and historical)
    and historical assignment rows are removed along with the group.

    TODO: the cascade/soft-delete semantics here are provisional — same posture as
    delete_role.
    """
    group = await get_group(group_id, session)
    active = (
        await session.exec(
            select(GroupRoleAssignment.id)
            .where(GroupRoleAssignment.group_id == group_id, GroupRoleAssignment.is_deleted == False)
            .limit(1)
        )
    ).first()
    if active is not None:
        raise GroupInUse(group_id)
    # The group_id foreign keys have no ON DELETE CASCADE, so remove dependents (membership
    # rows and historical soft-deleted assignments) in bulk before deleting the group itself.
    await session.execute(delete(GroupMembership).where(col(GroupMembership.group_id) == group_id))
    await session.execute(delete(GroupRoleAssignment).where(col(GroupRoleAssignment.group_id) == group_id))
    await session.delete(group)
    await record_event(
        session,
        GroupDeletedAuditEvent(
            outcome=AuditOutcome.SUCCESS,
            target=_target(group_id),
            change=AuditChange(old=_create_audit_snapshot(group)),
        ),
    )
    await session.commit()


async def _find_active_membership(user_id: int, group_id: int, session: AsyncSession) -> GroupMembership | None:
    """Return the user's active membership row in the group, or None."""
    statement = (
        select(GroupMembership)
        .where(
            GroupMembership.user_id == user_id,
            GroupMembership.group_id == group_id,
            GroupMembership.is_deleted == False,
        )
        .limit(1)
    )
    return (await session.exec(statement)).first()


async def add_group_member(user_id: int, group_id: int, session: AsyncSession) -> GroupMembership:
    """Return the user's active membership in the group, creating it if absent.

    Idempotent and race-safe under the same savepoint pattern as assign_role. Raises
    GroupNotFound. Rows are recorded with source="manual"; rule-derived rows will be owned
    by dynamic-membership recompute and are never created here. Creating the membership
    records ``group.member_added``; returning an existing one records nothing.
    """
    await get_group(group_id, session)
    existing = await _find_active_membership(user_id, group_id, session)
    if existing is not None:
        return existing
    try:
        # Insert inside a savepoint so a unique-index violation rolls back cleanly without
        # poisoning the surrounding transaction.
        async with session.begin_nested():
            membership = GroupMembership(user_id=user_id, group_id=group_id)
            session.add(membership)
            await session.flush()
    except IntegrityError:
        # A concurrent add inserted the same (user, group) after our check; return that
        # winner to stay idempotent, re-raise if it's somehow still not visible.
        winner = await _find_active_membership(user_id, group_id, session)
        if winner is None:
            raise
        return winner
    await record_event(
        session,
        GroupMemberAddedAuditEvent(
            outcome=AuditOutcome.SUCCESS, target=_target(group_id), change=AuditChange(new={"user_id": user_id})
        ),
    )
    return membership


async def remove_group_member(user_id: int, group_id: int, session: AsyncSession) -> None:
    """Soft-delete the user's active memberships in the group (a no-op when there are none).

    Removing an active membership records ``group.member_removed``; a no-op records nothing.
    """
    statement = select(GroupMembership).where(
        GroupMembership.user_id == user_id,
        GroupMembership.group_id == group_id,
        GroupMembership.is_deleted == False,
    )
    memberships = (await session.exec(statement)).all()
    for membership in memberships:
        membership.soft_delete()
    await session.flush()
    if memberships:
        await record_event(
            session,
            GroupMemberRemovedAuditEvent(
                outcome=AuditOutcome.SUCCESS, target=_target(group_id), change=AuditChange(old={"user_id": user_id})
            ),
        )


async def get_group_members(group_id: int, session: AsyncSession) -> list[int]:
    """Return the user ids of the group's active members. Raises GroupNotFound."""
    await get_group(group_id, session)
    result = await session.exec(
        select(GroupMembership.user_id).where(
            GroupMembership.group_id == group_id,
            GroupMembership.is_deleted == False,
        )
    )
    return list(result.all())


async def _find_active_group_assignment(
    group_id: int,
    role_id: int,
    permission_scope: PermissionScope,
    scope_object_id: str | None,
    session: AsyncSession,
) -> GroupRoleAssignment | None:
    """Return the group's active assignment of role_id at the exact scope, or None."""
    statement = (
        select(GroupRoleAssignment)
        .where(
            GroupRoleAssignment.group_id == group_id,
            GroupRoleAssignment.role_id == role_id,
            GroupRoleAssignment.scope == permission_scope.name,
            GroupRoleAssignment.scope_object_id == scope_object_id,
            GroupRoleAssignment.is_deleted == False,
        )
        .limit(1)
    )
    return (await session.exec(statement)).first()


async def assign_role_to_group(
    group_id: int,
    role_name: str,
    permission_scope: PermissionScope,
    scope_object_id: str | None,
    session: AsyncSession,
) -> GroupRoleAssignment:
    """Return the active assignment of role_name to the group at the scope, creating it if absent.

    Idempotent and race-safe (savepoint + re-query, like assign_role). Raises GroupNotFound,
    RoleNotFound, or InvalidScopeObjectId if the (scope, object id) pairing is invalid.
    Creating the assignment records ``group.role_assigned``; returning an existing one
    records nothing.
    """
    permission_scope.validate_object_id(scope_object_id)
    await get_group(group_id, session)
    role = (await session.exec(select(Role).where(Role.name == role_name))).one_or_none()
    if role is None or role.id is None:
        raise RoleNotFound(role_name)
    existing = await _find_active_group_assignment(group_id, role.id, permission_scope, scope_object_id, session)
    if existing is not None:
        return existing
    try:
        # Insert inside a savepoint so a unique-index violation rolls back cleanly without
        # poisoning the surrounding transaction.
        async with session.begin_nested():
            assignment = GroupRoleAssignment(
                group_id=group_id, role_id=role.id, scope=permission_scope.name, scope_object_id=scope_object_id
            )
            session.add(assignment)
            await session.flush()
    except IntegrityError:
        # A concurrent assign inserted the same (group, role, scope) after our check; return
        # that winner to stay idempotent, re-raise if it's somehow still not visible.
        winner = await _find_active_group_assignment(group_id, role.id, permission_scope, scope_object_id, session)
        if winner is None:
            raise
        return winner
    await record_event(
        session,
        GroupRoleAssignedAuditEvent(
            outcome=AuditOutcome.SUCCESS,
            target=_target(group_id),
            change=AuditChange(new=_create_grant_audit_snapshot(role_name, permission_scope, scope_object_id)),
        ),
    )
    return assignment


async def revoke_role_from_group(
    group_id: int,
    role_name: str,
    permission_scope: PermissionScope,
    scope_object_id: str | None,
    session: AsyncSession,
) -> None:
    """Soft-delete all active assignments of role_name to the group at the exact scope.

    Revoking an active assignment records ``group.role_revoked``; a no-op records nothing.
    """
    statement = (
        select(GroupRoleAssignment)
        .join(Role, col(Role.id) == col(GroupRoleAssignment.role_id))
        .where(
            GroupRoleAssignment.group_id == group_id,
            Role.name == role_name,
            GroupRoleAssignment.scope == permission_scope.name,
            GroupRoleAssignment.scope_object_id == scope_object_id,
            GroupRoleAssignment.is_deleted == False,
        )
    )
    assignments = (await session.exec(statement)).all()
    for assignment in assignments:
        # Already tracked by the session (they came from this query), so mutating them marks
        # them dirty, no session.add needed.
        assignment.soft_delete()
    await session.flush()
    if assignments:
        await record_event(
            session,
            GroupRoleRevokedAuditEvent(
                outcome=AuditOutcome.SUCCESS,
                target=_target(group_id),
                change=AuditChange(old=_create_grant_audit_snapshot(role_name, permission_scope, scope_object_id)),
            ),
        )


async def get_group_roles(group_id: int, session: AsyncSession) -> list[GroupRoleAssignment]:
    """Return the group's active role assignments, oldest first. Raises GroupNotFound."""
    await get_group(group_id, session)
    result = await session.exec(
        select(GroupRoleAssignment)
        .where(
            GroupRoleAssignment.group_id == group_id,
            GroupRoleAssignment.is_deleted == False,
        )
        .order_by(col(GroupRoleAssignment.id))
    )
    return list(result.all())
