from sparkth.core.permissions.constants import SCOPE_PATH_SEPARATOR, SCOPE_SEGMENT_SEPARATOR
from sparkth.core.permissions.exceptions import InvalidScopeObjectId, PermissionScopeNotFound
from sparkth.lib.hooks import SingleNamedItemHook
from sparkth.lib.log import get_logger

logger = get_logger(__name__)


class PermissionScope:
    """A kind of boundary a role can be assigned at that names one object of its kind.

    This is the common case (e.g. ``course``, ``quiz`` — many instances, each identified by a
    ``scope_object_id``). The rarer singleton case that names no object (``global``, ``whitelist``)
    is :class:`ObjectlessPermissionScope`, a subclass that overrides the object-id rules, the
    ``require()`` wiring, and how the scope cascades.

    Declared at module level in a plugin's ``plugin.py`` (or ``sparkth.core.permissions.scopes``
    for core scopes) via ``create()``. Each scope may have a single ``parent``, forming a chain
    from a specific kind up to a broader one; a scope with no parent is a root. The hierarchy
    lets a grant at an ancestor scope cascade to its descendants — see :meth:`scope_chain`.
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

        Use this, not the bare constructor — the constructor does not register (it is
        internal/test-only). A ``parent`` must already be registered; ancestors are never
        auto-created, so passing an unregistered parent raises ``PermissionScopeNotFound``.
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

    def scope_chain(self, scope_path: str | None) -> list[tuple[str, str | None]]:
        """The ``(scope name, object id)`` entries, leaf first, where a grant authorizes a check at this scope.

        If ``scope_path`` is set, the chain is every ``name:id`` segment of the path, then this scope's
        objectless ancestors (id ``None``). The path must end at a segment named after this scope, and
        any segments before it must be this scope's object-bearing ancestors, nearest last. A segment
        without a ``:``, or a path that breaks either rule, raises ``ValueError``. For ``quiz`` under
        ``course`` under ``org`` under ``global``, ``quiz.scope_chain("org:5/course:123/quiz:777")`` is
        ``[("quiz", "777"), ("course", "123"), ("org", "5"), ("global", None)]``.

        If ``scope_path`` is ``None``, the chain is this scope without an object, then its
        objectless ancestors. For the same ``quiz``, ``quiz.scope_chain(None)`` is
        ``[("quiz", None), ("global", None)]``.
        """
        scope_chain: list[tuple[str, str | None]]
        if scope_path is None:
            scope_chain = [(self.name, None)]
        else:
            # Each path segment is ``name:id``; split on the first separator so an id may contain it.
            scope_chain = []
            for segment in reversed(scope_path.split(SCOPE_PATH_SEPARATOR)):
                name, separator, object_id = segment.partition(SCOPE_SEGMENT_SEPARATOR)
                if not separator:
                    raise ValueError(f"Invalid scope path segment {segment!r} in {scope_path!r}")
                scope_chain.append((name, object_id))
            # The names, leaf first, must be this scope then its object-bearing ancestors in order; a
            # shorter path (down to a single segment) is allowed, a different or extra segment is not.
            names = [name for name, _ in scope_chain]
            expected = [
                self.name,
                *(p.name for p in self.get_parents() if not isinstance(p, ObjectlessPermissionScope)),
            ]
            if names != expected[: len(names)]:
                raise ValueError(f"Scope path {scope_path!r} does not follow the ancestors of {self.name!r}")
        for ancestor in self.get_parents():
            scope_chain.extend(ancestor._cascade_pairs())
        return scope_chain

    def validate_object_id(self, scope_object_id: str | None) -> None:
        """Raise ``InvalidScopeObjectId`` unless ``scope_object_id`` names an object.

        An object-bearing scope must name which object; enforced by ``assign_role`` in place of a
        DB CHECK, so the database stays ignorant of the scope vocabulary (which lives in the
        ``PERMISSION_SCOPES`` hook).
        """
        if scope_object_id is None:
            logger.warning("Object-bearing scope %r requires an object id", self.name)
            raise InvalidScopeObjectId(self.name, scope_object_id)

    def validate_names_object(self, names_object: bool) -> None:
        """Raise ``ValueError`` unless a route names the object this scope checks at.

        An object-bearing scope needs a route that names its object (a path parameter, a fixed id or a
        dependency). Called by ``Permission.require`` and ``Permission.require_for_object`` at
        route-definition/import time so a misconfiguration fails fast at startup rather than as a
        silent per-request denial.
        """
        if not names_object:
            raise ValueError(
                f"Scope {self.name!r} is object-bearing; name its object with a scope_param in require() "
                "or use require_for_object()"
            )

    def validate_listable(self) -> None:
        """Raise ``ValueError`` unless this scope has objects to list.

        An object-bearing scope has objects, so there is nothing to refuse. Called by
        ``Permission.require_for_any_object`` at route-definition time.
        """

    def _cascade_pairs(self) -> list[tuple[str, str | None]]:
        """This scope's contribution to a descendant's :meth:`scope_chain` when it is an ancestor.

        An object-bearing ancestor contributes nothing here: its object id comes from the
        descendant's materialized path instead.
        """
        return []


class ObjectlessPermissionScope(PermissionScope):
    """A singleton scope that names no object — there is exactly one (e.g. ``global``,
    ``whitelist``), so its ``role_assignment`` rows carry ``scope_object_id = NULL``."""

    def validate_object_id(self, scope_object_id: str | None) -> None:
        if scope_object_id is not None:
            logger.warning("Objectless scope %r was given object id %r", self.name, scope_object_id)
            raise InvalidScopeObjectId(self.name, scope_object_id)

    def validate_names_object(self, names_object: bool) -> None:
        if names_object:
            raise ValueError(
                f"Scope {self.name!r} is objectless and names no object; use require() without a scope_param"
            )

    def validate_listable(self) -> None:
        raise ValueError(f"Scope {self.name!r} is objectless and names no objects to list")

    def _cascade_pairs(self) -> list[tuple[str, str | None]]:
        # A singleton names no object, so it cascades to every descendant with a NULL id.
        return [(self.name, None)]


def build_scope_path(scope: PermissionScope, scope_id: str, parent_path: str | None = None) -> str:
    """Return the materialized path of an object: its parent's path, then ``<scope name>:<scope_id>``.

    Segments are joined by ``/``, root first (``org:5/course:123``); a root-level object has no
    ``parent_path``. A ``scope_id`` containing ``/`` raises ``InvalidScopeObjectId``, since it would add
    ancestor segments to the path. ``PermissionScope.scope_chain`` reads the same format back.
    """
    if SCOPE_PATH_SEPARATOR in scope_id:
        raise InvalidScopeObjectId(scope.name, scope_id)
    segment = f"{scope.name}{SCOPE_SEGMENT_SEPARATOR}{scope_id}"
    return segment if parent_path is None else f"{parent_path}{SCOPE_PATH_SEPARATOR}{segment}"


# Every scope kind the platform knows; <class>.create() registers each one here.
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
GLOBAL = ObjectlessPermissionScope.create("global")

# The whitelist is a singleton feature (there is exactly one registration whitelist), so it is an
# objectless container scope under GLOBAL. A role assigned at this scope manages the whole
# whitelist; a GLOBAL grant cascades down to it. See issue #489.
WHITELIST = ObjectlessPermissionScope.create("whitelist", parent=GLOBAL)

# Role management is delegable per-role: a role assigned at this scope authorizes managing one
# specific role (named by scope_object_id — the role's id), rather than every role. It is an
# object-bearing PermissionScope (there are many roles) hanging off GLOBAL, so a GLOBAL grant
# cascades down to it and existing global admins keep full role-management authority. See #490.
ROLE = PermissionScope.create("role", parent=GLOBAL)

# Group management is delegable per-group: a role assigned at this scope authorizes managing one
# specific group (named by scope_object_id — the group's id), rather than every group. It is an
# object-bearing PermissionScope hanging off GLOBAL, so a GLOBAL grant cascades down to it and
# existing global admins keep full group-management authority.
GROUP = PermissionScope.create("group", parent=GLOBAL)

# A user's own records (conversations, keys, files) live at the user scope, named by the user's id,
# so a grant at one user reaches that user's records and a GLOBAL grant reaches every user's.
USER = PermissionScope.create("user", parent=GLOBAL)
