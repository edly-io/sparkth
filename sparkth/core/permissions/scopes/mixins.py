from typing import ClassVar

from sqlmodel import Field, SQLModel

from sparkth.core.permissions.scopes import PermissionScope


class ScopeObjectMixin(SQLModel):
    """Mixin for a table model that is an object of a permission scope.

    The adopting model sets the class-level ``scope`` and stores ``scope_path``, the
    materialized path of the object, so a role granted at any
    ancestor object authorizes the object. ``scope_id`` is the object's ``id`` as a string; a
    model keyed otherwise overrides it.
    """

    scope: ClassVar[PermissionScope]
    scope_path: str = Field(index=True)

    @property
    def scope_id(self) -> str:
        """The object's id as a string."""
        return str(getattr(self, "id"))
