"""Role CRUD and role-permission grant management backing the role-management API.

Module-level async functions, consistent with the engine in this package. The
role-management API (``sparkth/api/v1/permissions``) imports them from here directly.
Every change is recorded as a ``role.*`` audit event in the same transaction as the
change itself (``delete_role`` also records ``group.role_revoked`` for the group assignments it
removes); an idempotent call that changes nothing records nothing.
"""

from sqlalchemy import delete
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.permissions import (
    PERMISSIONS,
    _record_active_group_grants_removed,
    _record_active_user_grants_removed,
    delete_grants_at_object,
    get_permission,
)
from sparkth.core.permissions.exceptions import (
    RoleAlreadyExists,
    RoleNotDeletable,
    RoleNotFound,
)
from sparkth.core.permissions.models import GroupRoleAssignment, Role, RoleAssignment, RolePermission
from sparkth.core.permissions.scopes import ROLE
from sparkth.lib.audit import record_event
from sparkth.lib.audit.events import (
    AuditChange,
    AuditOutcome,
    AuditTarget,
    RoleCreatedAuditEvent,
    RoleDeletedAuditEvent,
    RolePermissionGrantedAuditEvent,
    RolePermissionRevokedAuditEvent,
    RoleUpdatedAuditEvent,
)


def _target(role_id: int | None) -> AuditTarget:
    return AuditTarget(type="role", id=str(role_id))


def _create_audit_snapshot(role: Role) -> dict[str, str | None]:
    return {"name": role.name, "description": role.description}


async def create_role(name: str, description: str | None, session: AsyncSession) -> Role:
    """Create and return a role, recording ``role.created``.

    Raises RoleAlreadyExists if the name is already taken.
    """
    if (await session.exec(select(Role).where(Role.name == name))).first() is not None:
        raise RoleAlreadyExists(name)
    role = Role(name=name, description=description)
    session.add(role)
    await session.flush()
    await record_event(
        session,
        RoleCreatedAuditEvent(
            outcome=AuditOutcome.SUCCESS, target=_target(role.id), change=AuditChange(new=_create_audit_snapshot(role))
        ),
    )
    await session.commit()
    await session.refresh(role)
    return role


async def list_roles(session: AsyncSession) -> list[Role]:
    """Return every role, oldest first."""
    return list((await session.exec(select(Role).order_by(col(Role.id)))).all())


async def get_role(role_id: int, session: AsyncSession, for_update: bool = False) -> Role:
    """Return the role with role_id, or raise RoleNotFound.

    ``for_update`` locks the row until the transaction ends (a no-op on SQLite).
    """
    role = await session.get(Role, role_id, with_for_update=for_update)
    if role is None:
        raise RoleNotFound(str(role_id))
    return role


async def update_role(role_id: int, name: str | None, description: str | None, session: AsyncSession) -> Role:
    """Update a role's name and/or description, record ``role.updated``, and return it.

    A None argument leaves that field unchanged; an update that changes nothing records
    nothing. Raises RoleNotFound if the role is missing, or RoleAlreadyExists if name
    collides with another role.
    """
    role = await get_role(role_id, session)
    before = _create_audit_snapshot(role)
    if name is not None and name != role.name:
        if (await session.exec(select(Role).where(Role.name == name))).first() is not None:
            raise RoleAlreadyExists(name)
        role.name = name
    if description is not None:
        role.description = description
    if _create_audit_snapshot(role) == before:
        return role
    role.update_timestamp()
    session.add(role)
    await record_event(
        session,
        RoleUpdatedAuditEvent(
            outcome=AuditOutcome.SUCCESS,
            target=_target(role.id),
            change=AuditChange(old=before, new=_create_audit_snapshot(role)),
        ),
    )
    await session.commit()
    await session.refresh(role)
    return role


async def _delete_role_dependents(role_id: int, session: AsyncSession) -> None:
    """Delete the role's permission grants and every assignment of it, recording the active ones.

    The role_id foreign keys have no ON DELETE CASCADE, so dependents go before the role itself.
    """
    await _record_active_user_grants_removed(col(RoleAssignment.role_id) == role_id, session)
    await _record_active_group_grants_removed(col(GroupRoleAssignment.role_id) == role_id, session)
    for model in (RolePermission, RoleAssignment, GroupRoleAssignment):
        await session.exec(delete(model).where(col(model.role_id) == role_id))
    await session.flush()


async def delete_role(role_id: int, session: AsyncSession) -> None:
    """Delete a role together with everything that references it, recording ``role.deleted``.

    Raises RoleNotFound if the role is missing or RoleNotDeletable if it is marked non-deletable.
    Removes the role's permission grants, every user and group assignment of it (active and
    revoked), and every grant scoped to the role itself (``role:<id>``), in one transaction.
    Each active user assignment records ``role.unassigned`` and each active group assignment
    ``group.role_revoked`` before ``role.deleted``. The role row is locked for the delete so
    concurrent assignments wait for it.
    """
    role = await get_role(role_id, session, True)
    if not role.deletable:
        raise RoleNotDeletable(role.name)
    await delete_grants_at_object(ROLE, str(role_id), session)
    await _delete_role_dependents(role_id, session)
    await session.delete(role)
    await record_event(
        session,
        RoleDeletedAuditEvent(
            outcome=AuditOutcome.SUCCESS, target=_target(role_id), change=AuditChange(old=_create_audit_snapshot(role))
        ),
    )
    await session.commit()


async def add_role_permission(role_id: int, permission: str, session: AsyncSession) -> Role:
    """Grant permission to the role (idempotent: a no-op if it's already granted) and return the role.

    A new grant records ``role.permission_granted``; a no-op records nothing. Returning the
    role lets callers build a response without re-fetching it. Raises RoleNotFound
    (no such role) or PermissionNotFound (permission is not registered).
    """
    role = await get_role(role_id, session)
    get_permission(permission)
    existing = (
        await session.exec(
            select(RolePermission).where(
                RolePermission.role_id == role_id,
                RolePermission.permission == permission,
            )
        )
    ).first()
    if existing is None:
        session.add(RolePermission(role_id=role_id, permission=permission))
        await record_event(
            session,
            RolePermissionGrantedAuditEvent(
                outcome=AuditOutcome.SUCCESS,
                target=_target(role_id),
                change=AuditChange(new={"permission": permission}),
            ),
        )
        await session.commit()
    return role


async def remove_role_permission(role_id: int, permission: str, session: AsyncSession) -> None:
    """Revoke permission from the role (idempotent: a no-op if it isn't granted).

    Revoking a held grant records ``role.permission_revoked``; a no-op records nothing.
    Raises RoleNotFound if the role is missing.
    """
    await get_role(role_id, session)
    grant = (
        await session.exec(
            select(RolePermission).where(
                RolePermission.role_id == role_id,
                RolePermission.permission == permission,
            )
        )
    ).first()
    if grant is not None:
        await session.delete(grant)
        await record_event(
            session,
            RolePermissionRevokedAuditEvent(
                outcome=AuditOutcome.SUCCESS,
                target=_target(role_id),
                change=AuditChange(old={"permission": permission}),
            ),
        )
        await session.commit()


async def get_role_permissions(role_id: int, session: AsyncSession) -> list[str]:
    """Return the permission strings the role grants."""
    result = await session.exec(select(RolePermission.permission).where(RolePermission.role_id == role_id))
    return list(result.all())


async def get_permissions_for_roles(role_ids: list[int], session: AsyncSession) -> dict[int, list[str]]:
    """Return a {role_id: [permission, ...]} map for the given roles, fetched in a single query.

    Every requested role_id is present in the result (roles with no grants map to an empty list).
    Batches what would otherwise be one get_role_permissions() call per role into one SELECT.
    """
    permissions_by_role: dict[int, list[str]] = {role_id: [] for role_id in role_ids}
    if not role_ids:
        return permissions_by_role
    result = await session.exec(
        select(RolePermission.role_id, RolePermission.permission).where(col(RolePermission.role_id).in_(role_ids))
    )
    for role_id, permission in result.all():
        permissions_by_role[role_id].append(permission)
    return permissions_by_role


def available_permissions() -> list[str]:
    """Return every registered permission string — the vocabulary assignable to roles."""
    return [permission.name for permission in PERMISSIONS.iter_values()]
