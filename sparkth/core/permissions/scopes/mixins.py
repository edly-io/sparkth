from typing import ClassVar

from sqlmodel import Field, SQLModel

from sparkth.core.permissions.scopes import PermissionScope


def build_scope_path(scope: PermissionScope, scope_id: str, parent_path: str | None = None) -> str:
    """Return the materialized path of an object: its parent's path, then ``<scope name>:<scope_id>``.

    Segments are joined by ``/``, root first (``org:5/course:123``); a root-level object has no
    ``parent_path``. A ``scope_id`` containing ``/`` raises ``ValueError``, since it would add
    ancestor segments to the path.
    """
    if "/" in scope_id:
        raise ValueError(f"Scope id {scope_id!r} must not contain '/'")
    segment = f"{scope.name}:{scope_id}"
    return segment if parent_path is None else f"{parent_path}/{segment}"


class ScopeableMixin(SQLModel):
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
