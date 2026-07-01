from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from app.core.permissions.exceptions import PermissionScopeNotFound
from app.core.permissions.scopes import GLOBAL, PERMISSION_SCOPES
from app.lib.hooks import SingleNamedItemHook

if TYPE_CHECKING:
    from app.models.user import User


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

    def require_in_global_scope(self) -> Callable[..., Awaitable["User"]]:
        """Return a FastAPI dependency enforcing this permission at the GLOBAL scope.

        The dependency resolves the current user, checks the permission with no scope object
        id, returns the authenticated ``User`` on success, and raises 403 otherwise.
        """
        from app.core.permissions.dependency import build_permission_dependency

        return build_permission_dependency(self, GLOBAL, None)

    def require(self, permission_scope: str, scope_param: str) -> Callable[..., Awaitable["User"]]:
        """Return a FastAPI dependency enforcing this permission at a named scope.

        Args:
            permission_scope: A registered scope kind's name (e.g. ``"course"``). Looked up on
                the PERMISSION_SCOPES hook; an unregistered name raises ``PermissionScopeNotFound``
                here (at route-definition/import time) so misconfiguration fails fast at startup.
            scope_param: The name of the route's path parameter carrying the scope object id;
                resolved from ``request.path_params`` on each request.
        """
        from app.core.permissions.dependency import build_permission_dependency

        scope = PERMISSION_SCOPES.get(permission_scope)
        if scope is None:
            raise PermissionScopeNotFound(permission_scope)
        return build_permission_dependency(self, scope, scope_param)


# Every permission the platform knows; Permission.create() registers each one here.
# This hook is the single source of truth — app.lib.permissions.registry.PermissionsRegistry
# only reads from it.
PERMISSIONS: SingleNamedItemHook[Permission] = SingleNamedItemHook()

# Core Permissions shipped with the application.

# The email-whitelist permissions gate the registration email whitelist.
EMAIL_WHITELIST_READ = Permission.create("email.whitelist.read")
EMAIL_WHITELIST_CREATE = Permission.create("email.whitelist.create")
EMAIL_WHITELIST_DELETE = Permission.create("email.whitelist.delete")
