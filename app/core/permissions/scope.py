class PermissionScope:
    """A PermissionScope level that a plugin contributes to :data:`PERMISSION_SCOPE` hook

    The plugin registers it from its ``__init__`` with
    ``PERMISSION_SCOPE.add_item(self, PermissionScope(<scope_name>, parent=<parent_scope_object>))``.

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

    def get_parents(self) -> list["PermissionScope"]:
        """Return this scope's ancestors, nearest first.

        Walks up the hierarchy and returns ``[parent, grandparent, …]`` ending at the
        root. Returns an empty list when this scope has no parent.
        """
        if not self.parent:
            return []
        grand_parents = self.parent.get_parents()
        return [self.parent, *grand_parents]
