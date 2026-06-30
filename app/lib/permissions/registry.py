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

    # The hook is a constructor argument (defaulting to the global PERMISSIONS) rather than a
    # class attribute so tests can inject a fresh, isolated hook — the global hook can never be
    # emptied, so injection is the only patch-free way to give a test its own vocabulary.
    def __init__(self, hook: SingleNamedItemHook[Permission] = PERMISSIONS) -> None:
        self._hook = hook

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

    # The hook is constructor-injected for test isolation; see PermissionsRegistry for why.
    def __init__(self, hook: SingleNamedItemHook[PermissionScope] = PERMISSION_SCOPES) -> None:
        self._hook = hook

    def get(self, name: str) -> PermissionScope:
        """Return the registered scope kind named ``name``, or raise PermissionScopeNotFound."""
        permission_scope = self._hook.get(name)
        if permission_scope is None:
            raise PermissionScopeNotFound(name)
        return permission_scope
