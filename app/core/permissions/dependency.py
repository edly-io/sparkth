"""FastAPI dependency factory for permission-gated routes.

`Permission.require*` delegate here. The returned closure resolves the current user,
checks the permission with `can`, returns the authenticated `User`, and raises 403 on
denial / 500 on a misconfigured path parameter.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from fastapi import Depends, HTTPException, Request, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.permissions.scopes import PermissionScope
from app.core.permissions.utils import can
from app.lib.auth import get_current_user
from app.lib.db import get_async_session
from app.lib.log import get_logger
from app.models.user import User

if TYPE_CHECKING:
    from app.core.permissions import Permission

logger = get_logger(__name__)


def build_permission_dependency(
    permission: Permission,
    permission_scope: PermissionScope,
    scope_param: str | None,
) -> Callable[..., Awaitable[User]]:
    """Return a FastAPI dependency enforcing `permission` at `permission_scope`.

    `scope_param`, when set, names the path parameter whose value is the scope object id;
    it is resolved from `request.path_params` on each request (the value does not exist when
    the dependency is built). A `scope_param` the route does not provide is a wiring error and
    raises 500, never a silent 403.
    """

    async def _require_permission(
        request: Request,
        current_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_async_session),
    ) -> User:
        if scope_param is not None and scope_param not in request.path_params:
            logger.error(
                "Permission dependency misconfigured: scope_param %r is not among the route's path params %s",
                scope_param,
                list(request.path_params),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Permission scope is misconfigured",
            )
        scope_object_id = request.path_params.get(scope_param) if scope_param else None
        if not await can(current_user, permission, permission_scope, scope_object_id, session):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
        return current_user

    return _require_permission
