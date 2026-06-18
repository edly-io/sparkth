"""Scoped-RBAC permission service. Authored with LLM (Claude) assistance."""

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.permissions import RoleAssignment, RolePermission
from app.models.user import User
from app.permissions.constants import SCOPE_GLOBAL


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
        if user.is_superuser:
            return True
        statement = (
            select(RolePermission.permission)
            .join(RoleAssignment, RoleAssignment.role_id == RolePermission.role_id)  # type: ignore[arg-type]
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
