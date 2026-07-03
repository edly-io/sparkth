from app.core.permissions.exceptions import PermissionScopeNotFound
from app.lib.hooks import SingleNamedItemHook


class PermissionScope:
    """A PermissionScope level that a plugin contributes to the :data:`PERMISSION_SCOPES` hook

    The plugin registers it from its ``__init__`` with
    ``PermissionScope.create(<scope_name>, parent=<parent_scope_object>)``.

    A scope is a named kind of boundary a role can be assigned at (e.g. ``global``,
    ``course``, ``quiz``). Each scope may have a single ``parent`` scope, forming a
    chain from a specific kind up to a broader one; a scope with no parent is a root.
    The hierarchy lets a role granted at a parent scope cascade to its descendants.
    """

    def __init__(self, name: str, parent: "PermissionScope | None" = None) -> None:
        """Create a scope.

        Args:
            name: The scope kind's identifier (e.g. ``course``).
            parent: The enclosing scope, or ``None`` if this scope is a root.
        """
        self.parent = parent
        self.name = name

    @classmethod
    def create(cls, name: str, parent: "PermissionScope | None" = None) -> "PermissionScope":
        """Create a scope kind and register it on the PERMISSION_SCOPES hook.

        Use this, not the bare ``PermissionScope(name)`` constructor — the constructor does
        not register (it is internal/test-only). A ``parent`` must already be registered;
        ancestors are never auto-created, so passing an unregistered parent raises
        ``PermissionScopeNotFound``.
        """
        if parent is not None:
            # Validate the parent is registered; raises PermissionScopeNotFound if it is not.
            get_permission_scope(parent.name)
        permission_scope = cls(name, parent)
        PERMISSION_SCOPES.add_item(permission_scope)
        return permission_scope

    def get_parents(self) -> list["PermissionScope"]:
        """Return this scope's ancestors, nearest first.

        Walks up the hierarchy and returns ``[parent, grandparent, …]`` ending at the
        root. Returns an empty list when this scope has no parent.
        """
        if not self.parent:
            return []
        grand_parents = self.parent.get_parents()
        return [self.parent, *grand_parents]


# Every scope kind the platform knows; PermissionScope.create() registers each one here.
# This hook is the single source of truth — get_permission_scope() resolves names against it.
PERMISSION_SCOPES: SingleNamedItemHook[PermissionScope] = SingleNamedItemHook()


def get_permission_scope(name: str) -> PermissionScope:
    """Return the registered scope kind named ``name``, or raise PermissionScopeNotFound."""
    permission_scope = PERMISSION_SCOPES.get(name)
    if permission_scope is None:
        raise PermissionScopeNotFound(name)
    return permission_scope


# Core Permisson Scopes shipped with the application, ordered root-first so each is registered after its parent.

# The root scope: it applies platform-wide and names no object. This is the canonical
# instance plugins should reference as a parent so the whole tree shares one root.
GLOBAL = PermissionScope.create("global")
