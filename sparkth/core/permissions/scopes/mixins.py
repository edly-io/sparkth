"""Model mixins for the objects a permission scope names.

``ScopeObjectMixin`` gives a table model the scope it belongs to and the path of the object,
which a permission check uses to find the grants that cover it.
"""

from typing import ClassVar

from sqlmodel import Field, SQLModel

from sparkth.core.permissions.scopes import PermissionScope, build_scope_path


class ScopeObjectMixin(SQLModel):
    """Mixin for a table model that is an object of a permission scope.

    The adopting model sets the class-level ``scope`` and stores ``parent_scope_path``, the
    materialized path of the object's parent (``None`` for a root-level object). ``scope_path``
    adds the object's own segment, so a role granted at any ancestor object authorizes the object
    and the stored path never holds the object's own id, which is unknown until it is inserted.
    ``scope_id`` is the object's ``id`` as a string; a model keyed otherwise overrides it.
    """

    scope: ClassVar[PermissionScope]
    parent_scope_path: str | None = Field(default=None, index=True)

    @property
    def scope_id(self) -> str:
        """The object's id as a string."""
        return str(getattr(self, "id"))

    @property
    def scope_path(self) -> str:
        """The materialized path of the object: its parent's path, then its own segment.

        Only meaningful once the object has an id.
        """
        return build_scope_path(self.scope, self.scope_id, self.parent_scope_path)
