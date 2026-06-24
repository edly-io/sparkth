"""Runtime registries for the permission vocabulary.

The :data:`PERMISSIONS` and :data:`PERMISSION_SCOPE` hooks collect raw contributions from
plugins; these registries materialize them into the structures the rest of the
system queries — a flat list of permission strings and a tree of scope kinds.
Each registry is a singleton: ``PermissionsRegistry()`` always returns the one
shared instance.
"""

from app.core.permissions.defaults import DEFAULT_PERMISSION_SCOPES, DEFAULT_PERMISSIONS
from app.core.permissions.exceptions import PermissionNotFound, PermissionScopeNotFound
from app.core.permissions.scope import PermissionScope
from app.lib.log import get_logger
from app.lib.permissions.hooks import PERMISSION_SCOPE, PERMISSIONS

logger = get_logger(__name__)


class SingletonRegistry:
    """Base for the permission vocabulary registries.

    Holds one shared instance per subclass and seeds the platform defaults once on
    construction. Subclasses implement :meth:`reset` to (re)build their storage and
    seed defaults; the base reuses it for the one-time seed and exposes it publicly.
    """

    instance: "SingletonRegistry | None" = None
    _seeded: bool = False

    def __new__(cls) -> "SingletonRegistry":
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    def __init__(self) -> None:
        # __new__ returns the shared instance, so __init__ runs on every call; seed once.
        if not self._seeded:
            self._seeded = True
            self.reset()

    def reset(self) -> None:
        """Drop every registered item and re-seed the platform defaults.

        Mainly for test isolation: ``clear()`` alone leaves the registry empty, which for
        scopes drops the ``global`` root and makes any later child registration fail.
        """
        raise NotImplementedError


class PermissionsRegistry(SingletonRegistry):
    """The set of registered permission strings, held in a flat list."""

    _permissions: list[str]

    def reset(self) -> None:
        self._permissions = []
        for permission in DEFAULT_PERMISSIONS:
            self.add(permission)

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
        """Drop every registered permission, without re-seeding (see reset())."""
        self._permissions.clear()


class PermissionScopesRegistry(SingletonRegistry):
    """The registered scope kinds, indexed by name.

    The scopes form a tree through each scope's upward ``parent`` link; the
    registry indexes them by name and ensures every ancestor of a registered
    scope is registered too.
    """

    _index: dict[str, PermissionScope]

    def reset(self) -> None:
        self._index = {}
        for permission_scope in DEFAULT_PERMISSION_SCOPES:
            self.add(permission_scope)

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
        """Drop every registered scope, without re-seeding (see reset())."""
        self._index.clear()


def initialize_permissions_registry() -> None:
    """Load every permission contributed through the PERMISSIONS hook into the registry."""
    registry = PermissionsRegistry()
    for _, permission in PERMISSIONS.iter_items():
        registry.add(permission)


def initialize_permission_scopes_registry() -> None:
    """Load every permission scope contributed through the PERMISSION_SCOPE hook into the registry."""
    registry = PermissionScopesRegistry()
    for _, permission_scope in PERMISSION_SCOPE.iter_items():
        registry.add(permission_scope)
