"""Runtime registries for the permission vocabulary.

The :data:`PERMISSIONS` and :data:`PERMISSION_SCOPES` hooks collect the permissions and
scope kinds the platform knows; these registries materialize them into the structures the
rest of the system queries — a flat list of permission strings and a tree of scope kinds.
Each registry is a singleton: ``PermissionsRegistry()`` always returns the one
shared instance.
"""

from typing import cast

from app.core.permissions.exceptions import PermissionNotFound, PermissionScopeNotFound
from app.core.permissions.hooks import PERMISSION_SCOPES, PERMISSIONS
from app.core.permissions.scopes import PermissionScope
from app.lib.log import get_logger

logger = get_logger(__name__)


class PermissionsRegistry:
    """The set of registered permission strings, held in a flat list."""

    instance: "PermissionsRegistry | None" = None
    _permissions: list[str]

    def __new__(cls) -> "PermissionsRegistry":
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    def __init__(self) -> None:
        # __new__ returns the shared instance, so __init__ runs on every call;
        # guard the storage so an existing registry is never reset.
        if not hasattr(self, "_permissions"):
            self._permissions = []

    def add(self, permission: str) -> str:
        """Register permission and return it. A duplicate is logged and ignored."""
        if permission in self._permissions:
            logger.warning("Permission already registered, ignoring duplicate: %s", permission)
            return permission
        self._permissions.append(permission)
        return permission

    def get(self, name: str) -> str:
        """Return the registered permission named name, or raise PermissionNotFound."""
        if name not in self._permissions:
            raise PermissionNotFound(name)
        return name

    def all(self) -> list[str]:
        """Return a copy of every registered permission."""
        return list(self._permissions)

    def clear(self) -> None:
        """Drop every registered permission."""
        self._permissions.clear()


class PermissionScopesRegistry:
    """The registered scope kinds, indexed by name.

    The scopes form a tree through each scope's upward ``parent`` link; the
    registry indexes them by name and ensures every ancestor of a registered
    scope is registered too.
    """

    instance: "PermissionScopesRegistry | None" = None
    _index: dict[str, PermissionScope]

    def __new__(cls) -> "PermissionScopesRegistry":
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    def __init__(self) -> None:
        # __new__ returns the shared instance, so __init__ runs on every call;
        # guard the storage so an existing registry is never reset.
        if not hasattr(self, "_index"):
            self._index = {}

    def add(self, permission_scope: PermissionScope) -> PermissionScope:
        """Register permission_scope and return it. A duplicate (by name) is logged and ignored.

        The permission scope's parent, if any, must already be registered; ancestors are
        never auto-created. Adding one whose parent is absent raises PermissionScopeNotFound.
        """
        existing = self._index.get(permission_scope.name)
        if existing is not None:
            logger.warning("Permission scope already registered, ignoring duplicate: %s", permission_scope.name)
            return existing
        if permission_scope.parent is not None and permission_scope.parent.name not in self._index:
            raise PermissionScopeNotFound(permission_scope.parent.name)
        self._index[permission_scope.name] = permission_scope
        return permission_scope

    def get(self, name: str) -> PermissionScope:
        """Return the registered permission scope named name, or raise PermissionScopeNotFound."""
        if name not in self._index:
            raise PermissionScopeNotFound(name)
        return self._index[name]

    def clear(self) -> None:
        """Drop every registered scope."""
        self._index.clear()


def initialize_permissions_registry() -> None:
    """Load every permission contributed through the PERMISSIONS hook into the registry."""
    registry = PermissionsRegistry()
    for permission in PERMISSIONS.iter_items():
        registry.add(permission.name)


def initialize_permission_scopes_registry() -> None:
    """Load every permission scope contributed through the PERMISSION_SCOPES hook into the registry."""
    registry = PermissionScopesRegistry()
    for permission_scope in PERMISSION_SCOPES.iter_items():
        # The hook is typed by the shared HasName bound; every item is in fact a
        # PermissionScope (added via PermissionScope.create), and the registry needs the
        # full type to resolve parents.
        registry.add(cast(PermissionScope, permission_scope))
