from abc import ABC, abstractmethod

from app.core.permissions.exceptions import InvalidScopeObjectId, PermissionScopeNotFound
from app.lib.hooks import SingleNamedItemHook
from app.lib.log import get_logger

logger = get_logger(__name__)


class PermissionScope(ABC):
    """A kind of boundary a role can be assigned at (e.g. ``global``, ``course``, ``quiz``).

    Declared from a plugin's ``__init__`` (or ``app.core.permissions.scopes`` for core scopes) via
    a concrete subclass's ``create()`` — :class:`ObjectlessScope` for a singleton that names no
    object (``global``, ``whitelist``), or :class:`ObjectScope` for a kind with many instances that
    each name one object (``course``, ``quiz``).

    Each scope may have a single ``parent``, forming a chain from a specific kind up to a broader
    one; a scope with no parent is a root. The hierarchy lets a grant at an ancestor scope cascade
    to its descendants — see :meth:`scope_chain`.
    """

    def __init__(self, name: str, parent: "PermissionScope | None" = None) -> None:
        """Create a scope.

        Args:
            name: The scope kind's identifier (e.g. ``course``).
            parent: The enclosing scope, or ``None`` if this scope is a root.
        """
        self.name = name
        self.parent = parent

    @classmethod
    def create(cls, name: str, parent: "PermissionScope | None" = None) -> "PermissionScope":
        """Create a scope kind and register it on the PERMISSION_SCOPES hook.

        Call this on a concrete subclass (``ObjectlessScope.create`` / ``ObjectScope.create``), not
        the bare constructor — the constructor does not register (it is internal/test-only). A
        ``parent`` must already be registered; ancestors are never auto-created, so passing an
        unregistered parent raises ``PermissionScopeNotFound``.
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
        return [self.parent, *self.parent.get_parents()]

    def scope_chain(self, scope_object_id: str | None) -> list[tuple[str, str | None]]:
        """The ``(scope name, object id)`` pairs a grant may occupy to satisfy a check at THIS
        scope with ``scope_object_id``.

        Always includes this scope itself carrying the checked id, then each ancestor's cascade
        contribution (see :meth:`_cascade_pairs`). The read-side checks (``can`` / ``has_role``)
        match a user's active assignments against these pairs — a grant at any one authorizes.
        """
        pairs: list[tuple[str, str | None]] = [(self.name, scope_object_id)]
        for ancestor in self.get_parents():
            pairs.extend(ancestor._cascade_pairs())
        return pairs

    @abstractmethod
    def validate_object_id(self, scope_object_id: str | None) -> None:
        """Raise ``InvalidScopeObjectId`` if ``scope_object_id`` is invalid for this scope kind.

        Enforced by ``assign_role`` in place of a DB CHECK, so the database stays ignorant of the
        scope vocabulary (which lives in the ``PERMISSION_SCOPES`` hook).
        """

    @abstractmethod
    def validate_scope_param(self, scope_param: str | None) -> None:
        """Raise ``ValueError`` if a route's ``scope_param`` wiring is wrong for this scope kind.

        Called by ``Permission.require`` at route-definition/import time so a misconfiguration
        fails fast at startup rather than as a silent per-request denial.
        """

    @abstractmethod
    def _cascade_pairs(self) -> list[tuple[str, str | None]]:
        """This scope's ``(name, object id)`` contribution to a descendant's :meth:`scope_chain`
        when it appears as an ancestor."""


class ObjectlessScope(PermissionScope):
    """A singleton scope that names no object — there is exactly one (e.g. ``global``,
    ``whitelist``), so its ``role_assignment`` rows carry ``scope_object_id = NULL``."""

    def validate_object_id(self, scope_object_id: str | None) -> None:
        if scope_object_id is not None:
            logger.warning("Objectless scope %r was given object id %r", self.name, scope_object_id)
            raise InvalidScopeObjectId(self.name, scope_object_id)

    def validate_scope_param(self, scope_param: str | None) -> None:
        if scope_param is not None:
            raise ValueError(
                f"Scope {self.name!r} is objectless and names no object; drop the scope_param {scope_param!r}"
            )

    def _cascade_pairs(self) -> list[tuple[str, str | None]]:
        # A singleton names no object, so it cascades to every descendant with a NULL id.
        return [(self.name, None)]


class ObjectScope(PermissionScope):
    """A scope with many instances that each name one object (e.g. ``course``, ``quiz``), so its
    ``role_assignment`` rows carry a non-``NULL`` ``scope_object_id``."""

    def validate_object_id(self, scope_object_id: str | None) -> None:
        if scope_object_id is None:
            logger.warning("Object-bearing scope %r requires an object id", self.name)
            raise InvalidScopeObjectId(self.name, scope_object_id)

    def validate_scope_param(self, scope_param: str | None) -> None:
        if scope_param is None:
            raise ValueError(
                f"Scope {self.name!r} is object-bearing; require() needs a scope_param naming its path parameter"
            )

    def _cascade_pairs(self) -> list[tuple[str, str | None]]:
        # Resolving which ancestor object a descendant belongs to needs a materialized path, so an
        # object-bearing ancestor does not cascade yet (deferred; see issue #420 Phase 2).
        return []


# Every scope kind the platform knows; <subclass>.create() registers each one here.
# This hook is the single source of truth — get_permission_scope() resolves names against it.
PERMISSION_SCOPES: SingleNamedItemHook[PermissionScope] = SingleNamedItemHook()


def get_permission_scope(name: str) -> PermissionScope:
    """Return the registered scope kind named ``name``, or raise PermissionScopeNotFound."""
    permission_scope = PERMISSION_SCOPES.get(name)
    if permission_scope is None:
        raise PermissionScopeNotFound(name)
    return permission_scope


# Core Permission Scopes shipped with the application, ordered root-first so each is registered
# after its parent.

# The root scope: it applies platform-wide and names no object. This is the canonical instance
# plugins should reference as a parent so the whole tree shares one root.
GLOBAL = ObjectlessScope.create("global")

# The whitelist is a singleton feature (there is exactly one registration whitelist), so it is an
# objectless container scope under GLOBAL. A role assigned at this scope manages the whole
# whitelist; a GLOBAL grant cascades down to it. See issue #489.
WHITELIST = ObjectlessScope.create("whitelist", parent=GLOBAL)
