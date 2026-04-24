from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.db import get_async_session
from app.models.rbac import RoleName
from app.models.user import User
from app.services import rbac as rbac_service


def require_role(
    role: RoleName,
) -> Callable[..., Coroutine[Any, Any, User]]:
    """Dependency factory: require the user to have a specific role. Superusers pass all role checks."""

    async def dependency(
        current_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_async_session),
    ) -> User:
        if not current_user.id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not authenticated",
            )
        if await rbac_service.is_superuser(session, current_user.id):
            return current_user
        if not await rbac_service.has_role(session, current_user.id, role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role",
            )
        return current_user

    return dependency


def require_permission(
    permission: str,
) -> Callable[..., Coroutine[Any, Any, User]]:
    """Dependency factory: require the user to have a specific permission. Superusers bypass all checks."""

    async def dependency(
        current_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_async_session),
    ) -> User:
        if not current_user.id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not authenticated",
            )
        if not await rbac_service.has_permission(session, current_user.id, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied",
            )
        return current_user

    return dependency


async def require_superuser(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> User:
    """Dependency: require the user to be a superuser."""
    if not current_user.id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated",
        )
    if not await rbac_service.is_superuser(session, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser required",
        )
    return current_user
