class Scope:
    """A scope kind and its position in the scope hierarchy.

    A scope is a named kind of boundary a role can be assigned at (e.g. ``global``,
    ``course``, ``quiz``). Each scope may have a single ``parent`` scope, forming a
    chain from a specific kind up to a broader one; a scope with no parent is a root.
    The hierarchy lets a role granted at a parent scope cascade to its descendants.
    """

    def __init__(self, name: str, parent: "Scope" | None = None) -> None:
        """Create a scope.

        Args:
            name: The scope kind's identifier (e.g. ``course``).
            parent: The enclosing scope, or ``None`` if this scope is a root.
        """
        self.parent = parent
        self.name = name

    def get_parents(self) -> list["Scope"]:
        """Return this scope's ancestors, nearest first.

        Walks up the hierarchy and returns ``[parent, grandparent, …]`` ending at the
        root. Returns an empty list when this scope has no parent.
        """
        if not self.parent:
            return []
        grand_parents = self.parent.get_parents()
        return [self.parent, *grand_parents]
