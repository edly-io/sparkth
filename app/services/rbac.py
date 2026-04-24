from typing import cast

from sqlalchemy import column as sa_col
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logger import get_logger
from app.models.rbac import Permission, RoleName, RolePermission, UserRole

logger = get_logger(__name__)

DEFAULT_PERMISSIONS: list[dict[str, str]] = [
    {"name": "users:list", "description": "List all users"},
    {"name": "users:read", "description": "Read any user profile"},
    {"name": "users:manage", "description": "Create, update, and deactivate users"},
    {"name": "users:assign_role", "description": "Assign or remove user roles"},
    {"name": "plugins:manage", "description": "Enable or disable plugins globally"},
]

ADMIN_PERMISSIONS: list[str] = [p["name"] for p in DEFAULT_PERMISSIONS]


async def assign_role(session: AsyncSession, user_id: int, role: RoleName) -> UserRole:
    """Assign a role to a user. Idempotent -- returns existing if already assigned."""
    statement = select(UserRole).where(UserRole.user_id == user_id, UserRole.role == role.value)
    result = await session.exec(statement)
    existing = result.one_or_none()

    if existing:
        return existing

    user_role = UserRole(user_id=user_id, role=role.value)
    session.add(user_role)
    await session.flush()
    return user_role


async def remove_role(session: AsyncSession, user_id: int, role: RoleName) -> None:
    """Remove a role from a user. No-op if role not assigned."""
    statement = select(UserRole).where(UserRole.user_id == user_id, UserRole.role == role.value)
    result = await session.exec(statement)
    existing = result.one_or_none()

    if existing:
        await session.delete(existing)
        await session.flush()


async def get_user_roles(session: AsyncSession, user_id: int) -> list[RoleName]:
    """Get all roles assigned to a user."""
    statement = select(UserRole.role).where(UserRole.user_id == user_id)
    result = await session.exec(statement)
    return [RoleName(r) for r in result.all()]


async def has_role(session: AsyncSession, user_id: int, role: RoleName) -> bool:
    """Check if a user has a specific role."""
    statement = select(UserRole).where(UserRole.user_id == user_id, UserRole.role == role.value)
    result = await session.exec(statement)
    return result.one_or_none() is not None


async def is_superuser(session: AsyncSession, user_id: int) -> bool:
    """Check if a user has the superuser role."""
    return await has_role(session, user_id, RoleName.SUPERUSER)


async def has_permission(session: AsyncSession, user_id: int, permission_name: str) -> bool:
    """
    Check if a user has a specific permission.

    Superusers bypass all permission checks (Django semantics).
    For other users, checks if any of their roles have the requested permission.
    """
    if await is_superuser(session, user_id):
        return True

    roles = await get_user_roles(session, user_id)
    if not roles:
        return False

    role_values = [r.value for r in roles]
    statement = (
        select(Permission.name)
        .join(RolePermission, RolePermission.permission_id == Permission.id)  # type: ignore[arg-type]
        .where(
            sa_col("role").in_(role_values),
            Permission.name == permission_name,
        )
    )
    result = await session.exec(statement)
    return result.one_or_none() is not None


async def get_role_permissions(session: AsyncSession, role: RoleName) -> list[str]:
    """Get all permission names assigned to a role."""
    statement = (
        select(Permission.name)
        .join(RolePermission, RolePermission.permission_id == Permission.id)  # type: ignore[arg-type]
        .where(RolePermission.role == role.value)
    )
    result = await session.exec(statement)
    return list(result.all())


async def seed_default_permissions(session: AsyncSession) -> None:
    """Seed default permissions and assign them to the admin role. Idempotent."""
    for perm_data in DEFAULT_PERMISSIONS:
        statement = select(Permission).where(Permission.name == perm_data["name"])
        result = await session.exec(statement)
        perm = result.one_or_none()

        if not perm:
            perm = Permission(name=perm_data["name"], description=perm_data["description"])
            session.add(perm)
            await session.flush()

        if perm_data["name"] in ADMIN_PERMISSIONS:
            perm_id = cast(int, perm.id)
            rp_statement = select(RolePermission).where(
                RolePermission.role == RoleName.ADMIN.value,
                RolePermission.permission_id == perm_id,
            )
            rp_result = await session.exec(rp_statement)
            if not rp_result.one_or_none():
                rp = RolePermission(role=RoleName.ADMIN.value, permission_id=perm_id)
                session.add(rp)
                await session.flush()
