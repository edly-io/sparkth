"""Scoped-RBAC permission service. Authored with LLM (Claude) assistance."""

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.user import User
from app.permissions.constants import SCOPE_GLOBAL
from app.permissions.exceptions import RoleNotFound
from app.permissions.models import Role, RoleAssignment, RolePermission


class PermissionService:
    """Resolves and mutates a user's role assignments. Holds the session."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def can(
        self,
        user: User,
        permission: str,
        scope_type: str = SCOPE_GLOBAL,
        scope_id: str | None = None,
    ) -> bool:
        statement = (
            select(RolePermission.permission)
            .join(RoleAssignment, col(RoleAssignment.role_id) == col(RolePermission.role_id))
            .where(
                RoleAssignment.user_id == user.id,
                RoleAssignment.is_deleted == False,
                RoleAssignment.scope_type == scope_type,
                RoleAssignment.scope_id == scope_id,
                RolePermission.permission == permission,
            )
            .limit(1)
        )
        result = await self.session.exec(statement)
        return result.first() is not None

    async def assign_role(
        self,
        user_id: int,
        role_name: str,
        scope_type: str = SCOPE_GLOBAL,
        scope_id: str | None = None,
    ) -> RoleAssignment:
        """Create a role assignment for user_id, raising RoleNotFound if the role does not exist."""
        role = (await self.session.exec(select(Role).where(Role.name == role_name))).one_or_none()
        if role is None or role.id is None:
            raise RoleNotFound(role_name)
        assignment = RoleAssignment(user_id=user_id, role_id=role.id, scope_type=scope_type, scope_id=scope_id)
        self.session.add(assignment)
        await self.session.flush()
        return assignment

    async def has_role(
        self,
        user_id: int,
        role_name: str,
        scope_type: str = SCOPE_GLOBAL,
        scope_id: str | None = None,
    ) -> bool:
        """Return True if user_id holds role_name at the given scope (active assignment)."""
        statement = (
            select(RoleAssignment.id)
            .join(Role, Role.id == RoleAssignment.role_id)  # type: ignore[arg-type]
            .where(
                RoleAssignment.user_id == user_id,
                Role.name == role_name,
                RoleAssignment.scope_type == scope_type,
                RoleAssignment.scope_id == scope_id,
                RoleAssignment.is_deleted == False,
            )
            .limit(1)
        )
        return (await self.session.exec(statement)).first() is not None

    async def revoke_role(
        self,
        user_id: int,
        role_name: str,
        scope_type: str = SCOPE_GLOBAL,
        scope_id: str | None = None,
    ) -> None:
        """Soft-delete all active assignments of role_name for user_id at the given scope."""
        statement = (
            select(RoleAssignment)
            .join(Role, col(Role.id) == col(RoleAssignment.role_id))
            .where(
                RoleAssignment.user_id == user_id,
                Role.name == role_name,
                RoleAssignment.scope_type == scope_type,
                RoleAssignment.scope_id == scope_id,
                RoleAssignment.is_deleted == False,
            )
        )
        assignments = (await self.session.exec(statement)).all()
        for assignment in assignments:
            assignment.soft_delete()
            self.session.add(assignment)
        await self.session.flush()
