"""Role CRUD and role-permission grant management backing the role-management API.

Module-level async functions, consistent with the engine in this package. The
role-management API (``app/api/v1/permissions``) imports them from here directly.
"""

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.permissions import PERMISSIONS, get_permission_or_raise
from app.core.permissions.exceptions import (
    RoleAlreadyExists,
    RoleInUse,
    RoleNotFound,
)
from app.core.permissions.models import Role, RoleAssignment, RolePermission


async def create_role(name: str, description: str | None, session: AsyncSession) -> Role:
    """Create and return a role. Raises RoleAlreadyExists if the name is already taken."""
    if (await session.exec(select(Role).where(Role.name == name))).first() is not None:
        raise RoleAlreadyExists(name)
    role = Role(name=name, description=description)
    session.add(role)
    await session.commit()
    await session.refresh(role)
    return role


async def list_roles(session: AsyncSession) -> list[Role]:
    """Return every role, oldest first."""
    return list((await session.exec(select(Role).order_by(col(Role.id)))).all())


async def get_role(role_id: int, session: AsyncSession) -> Role:
    """Return the role with role_id, or raise RoleNotFound."""
    role = await session.get(Role, role_id)
    if role is None:
        raise RoleNotFound(str(role_id))
    return role


async def update_role(role_id: int, name: str | None, description: str | None, session: AsyncSession) -> Role:
    """Update a role's name and/or description and return it.

    A None argument leaves that field unchanged. Raises RoleNotFound if the role is
    missing, or RoleAlreadyExists if name collides with another role.
    """
    role = await get_role(role_id, session)
    if name is not None and name != role.name:
        if (await session.exec(select(Role).where(Role.name == name))).first() is not None:
            raise RoleAlreadyExists(name)
        role.name = name
    if description is not None:
        role.description = description
    role.update_timestamp()
    session.add(role)
    await session.commit()
    await session.refresh(role)
    return role


async def delete_role(role_id: int, session: AsyncSession) -> None:
    """Delete a role together with its permission grants.

    Raises RoleNotFound if the role is missing, or RoleInUse if it still has an active
    assignment. Only active assignments block; historical (soft-deleted) assignment rows
    are removed along with the role.

    TODO: the cascade/soft-delete semantics here are provisional — revisit how a role's
    assignment history should be handled on delete.
    """
    role = await get_role(role_id, session)
    active = (
        await session.exec(
            select(RoleAssignment.id)
            .where(RoleAssignment.role_id == role_id, RoleAssignment.is_deleted == False)
            .limit(1)
        )
    ).first()
    if active is not None:
        raise RoleInUse(role_id)
    # The role_id foreign keys have no ON DELETE CASCADE, so remove dependents (grants and
    # any historical soft-deleted assignments) before deleting the role itself.
    for grant in (await session.exec(select(RolePermission).where(RolePermission.role_id == role_id))).all():
        await session.delete(grant)
    for assignment in (await session.exec(select(RoleAssignment).where(RoleAssignment.role_id == role_id))).all():
        await session.delete(assignment)
    await session.delete(role)
    await session.commit()


async def add_role_permission(role_id: int, permission: str, session: AsyncSession) -> None:
    """Grant permission to the role (idempotent — a no-op if it's already granted).

    Raises RoleNotFound (no such role) or PermissionNotFound (permission is not registered).
    """
    await get_role(role_id, session)
    get_permission_or_raise(permission)
    existing = (
        await session.exec(
            select(RolePermission).where(
                RolePermission.role_id == role_id,
                RolePermission.permission == permission,
            )
        )
    ).first()
    if existing is not None:
        return
    session.add(RolePermission(role_id=role_id, permission=permission))
    await session.commit()


async def remove_role_permission(role_id: int, permission: str, session: AsyncSession) -> None:
    """Revoke permission from the role (idempotent — a no-op if it isn't granted).

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
        await session.commit()


async def get_role_permissions(role_id: int, session: AsyncSession) -> list[str]:
    """Return the permission strings the role grants."""
    result = await session.exec(select(RolePermission.permission).where(RolePermission.role_id == role_id))
    return list(result.all())


def available_permissions() -> list[str]:
    """Return every registered permission string — the vocabulary assignable to roles."""
    return [permission.name for permission in PERMISSIONS.iter_values()]
