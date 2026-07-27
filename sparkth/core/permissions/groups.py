"""Group CRUD, membership, and group-role-grant management (issue #519).

Module-level async functions mirroring the role engine. The CRUD functions commit
(like ``roles.py``); the membership and assignment functions only flush (like
``assign_role`` / ``revoke_role``), so their callers own the transaction boundary.
Authored with LLM (Claude) assistance.
"""

from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.permissions.exceptions import (
    GroupAlreadyExists,
    GroupInUse,
    GroupNotFound,
    RoleNotFound,
)
from sparkth.core.permissions.models import Group, GroupMembership, GroupRoleAssignment, Role
from sparkth.core.permissions.scopes import PermissionScope


async def create_group(name: str, description: str | None, session: AsyncSession) -> Group:
    """Create and return a group. Raises GroupAlreadyExists if the name is already taken."""
    if (await session.exec(select(Group).where(Group.name == name))).first() is not None:
        raise GroupAlreadyExists(name)
    group = Group(name=name, description=description)
    session.add(group)
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
    """Update a group's name and/or description and return it.

    A None argument leaves that field unchanged. Raises GroupNotFound if the group is
    missing, or GroupAlreadyExists if name collides with another group.
    """
    group = await get_group(group_id, session)
    if name is not None and name != group.name:
        if (await session.exec(select(Group).where(Group.name == name))).first() is not None:
            raise GroupAlreadyExists(name)
        group.name = name
    if description is not None:
        group.description = description
    group.update_timestamp()
    session.add(group)
    await session.commit()
    await session.refresh(group)
    return group


async def delete_group(group_id: int, session: AsyncSession) -> None:
    """Delete a group together with its membership and assignment history.

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
    # rows and historical soft-deleted assignments) before deleting the group itself.
    for membership in (await session.exec(select(GroupMembership).where(GroupMembership.group_id == group_id))).all():
        await session.delete(membership)
    for assignment in (
        await session.exec(select(GroupRoleAssignment).where(GroupRoleAssignment.group_id == group_id))
    ).all():
        await session.delete(assignment)
    await session.delete(group)
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
    by dynamic-membership recompute and are never created here.
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
        return membership
    except IntegrityError:
        # A concurrent add inserted the same (user, group) after our check; return that
        # winner to stay idempotent, re-raise if it's somehow still not visible.
        winner = await _find_active_membership(user_id, group_id, session)
        if winner is None:
            raise
        return winner


async def remove_group_member(user_id: int, group_id: int, session: AsyncSession) -> None:
    """Soft-delete the user's active memberships in the group (a no-op when there are none)."""
    statement = select(GroupMembership).where(
        GroupMembership.user_id == user_id,
        GroupMembership.group_id == group_id,
        GroupMembership.is_deleted == False,
    )
    for membership in (await session.exec(statement)).all():
        membership.soft_delete()
    await session.flush()


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
        return assignment
    except IntegrityError:
        # A concurrent assign inserted the same (group, role, scope) after our check; return
        # that winner to stay idempotent, re-raise if it's somehow still not visible.
        winner = await _find_active_group_assignment(group_id, role.id, permission_scope, scope_object_id, session)
        if winner is None:
            raise
        return winner


async def revoke_role_from_group(
    group_id: int,
    role_name: str,
    permission_scope: PermissionScope,
    scope_object_id: str | None,
    session: AsyncSession,
) -> None:
    """Soft-delete all active assignments of role_name to the group at the exact scope."""
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
    for assignment in (await session.exec(statement)).all():
        # Already tracked by the session (they came from this query), so mutating them marks
        # them dirty — no session.add needed.
        assignment.soft_delete()
    await session.flush()


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
