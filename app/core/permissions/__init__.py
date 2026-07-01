from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Depends, HTTPException, Request, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.permissions.exceptions import PermissionScopeNotFound
from app.core.permissions.scopes import GLOBAL, PERMISSION_SCOPES, PermissionScope
from app.core.permissions.utils import can
from app.lib.auth import get_current_user
from app.lib.db import get_async_session
from app.lib.hooks import SingleNamedItemHook
from app.lib.log import get_logger
from app.models.user import User

logger = get_logger(__name__)


class Permission:
    def __init__(self, name: str) -> None:
        self.name = name

    @classmethod
    def create(cls, name: str) -> "Permission":
        """Create a permission and register it on the PERMISSIONS hook.

        Use this, not the bare ``Permission(name)`` constructor — the constructor does not
        register (it is internal/test-only), and an unregistered permission authorizes nothing.
        """
        permission = cls(name)
        PERMISSIONS.add_item(permission)
        return permission

    def _require_permission(
        self, permission_scope: PermissionScope, scope_param: str | None
    ) -> Callable[..., Awaitable[User]]:
        """Build the FastAPI dependency enforcing this permission at ``permission_scope``.

        Shared by ``require`` and ``require_in_global_scope``. FastAPI cannot inject the scope or
        ``scope_param`` (they are fixed when the route is declared, not per request), so this
        returns a closure that captures them and declares only the sub-dependencies FastAPI does
        resolve (the current user and the DB session).

        The dependency returns the authenticated ``User`` on success. ``scope_param``, when set,
        names the path parameter carrying the scope object id, resolved from
        ``request.path_params`` per request; a ``scope_param`` the route does not provide raises
        500 (a wiring error, never a silent 403), and a failed permission check raises 403.
        """

        async def dependency(
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
            if not await can(current_user, self, permission_scope, scope_object_id, session):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
            return current_user

        return dependency

    def require_in_global_scope(self) -> Callable[..., Awaitable[User]]:
        """Return a FastAPI dependency enforcing this permission at the GLOBAL scope.

        The dependency resolves the current user, checks the permission with no scope object
        id, returns the authenticated ``User`` on success, and raises 403 otherwise.
        """
        return self._require_permission(GLOBAL, None)

    def require(self, permission_scope: str, scope_param: str) -> Callable[..., Awaitable[User]]:
        """Return a FastAPI dependency enforcing this permission at a named scope.

        Args:
            permission_scope: A registered scope kind's name (e.g. ``"course"``). Looked up on
                the PERMISSION_SCOPES hook; an unregistered name raises ``PermissionScopeNotFound``
                here (at route-definition/import time) so misconfiguration fails fast at startup.
            scope_param: The name of the route's path parameter carrying the scope object id;
                resolved from ``request.path_params`` on each request.
        """
        scope = PERMISSION_SCOPES.get(permission_scope)
        if scope is None:
            raise PermissionScopeNotFound(permission_scope)
        return self._require_permission(scope, scope_param)


# Every permission the platform knows; Permission.create() registers each one here.
# This hook is the single source of truth — app.lib.permissions.registry.PermissionsRegistry
# only reads from it.
PERMISSIONS: SingleNamedItemHook[Permission] = SingleNamedItemHook()

# Core Permissions shipped with the application.

# The email-whitelist permissions gate the registration email whitelist.
EMAIL_WHITELIST_READ = Permission.create("email.whitelist.read")
EMAIL_WHITELIST_CREATE = Permission.create("email.whitelist.create")
EMAIL_WHITELIST_DELETE = Permission.create("email.whitelist.delete")
