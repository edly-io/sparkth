"""Read-only views over the permission vocabulary hooks.

The :data:`PERMISSIONS` and :data:`PERMISSION_SCOPES` hooks are the single source of truth for
the permissions and scope kinds the platform knows. These registries are thin read-only wrappers
over those hooks: they hold no vocabulary of their own and expose only lookups, translating a
miss into the matching domain exception.
"""

from app.core.permissions import PERMISSIONS, Permission
from app.core.permissions.exceptions import PermissionNotFound, PermissionScopeNotFound
from app.core.permissions.scopes import PERMISSION_SCOPES, PermissionScope
from app.lib.hooks import SingleNamedItemHook


class PermissionsRegistry:
    """Read-only view of the registered permissions, backed by the PERMISSIONS hook."""

    # In production the source is always the global PERMISSIONS hook, so it is a fixed class
    # attribute rather than a constructor argument. Unit tests patch it to inject an isolated hook.
    _hook: SingleNamedItemHook[Permission] = PERMISSIONS

    def get(self, name: str) -> Permission:
        """Return the registered permission named ``name``, or raise PermissionNotFound."""
        permission = self._hook.get(name)
        if permission is None:
            raise PermissionNotFound(name)
        return permission

    def all(self) -> list[Permission]:
        """Return every registered permission."""
        return list(self._hook.iter_values())


class PermissionScopesRegistry:
    """Read-only view of the registered scope kinds, backed by the PERMISSION_SCOPES hook."""

    # Fixed class attribute, patched in tests; see PermissionsRegistry.
    _hook: SingleNamedItemHook[PermissionScope] = PERMISSION_SCOPES

    def get(self, name: str) -> PermissionScope:
        """Return the registered scope kind named ``name``, or raise PermissionScopeNotFound."""
        permission_scope = self._hook.get(name)
        if permission_scope is None:
            raise PermissionScopeNotFound(name)
        return permission_scope
