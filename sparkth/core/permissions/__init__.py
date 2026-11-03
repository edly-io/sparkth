"""Core scoped-RBAC permissions: the vocabulary, the FastAPI gate, and the engine.

Holds the :class:`Permission` class and the ``PERMISSIONS`` hook (the permission
vocabulary), the shipped core permissions, the ``Permission.require*`` FastAPI
dependency layer, and the read-side checks (``can``, ``has_role``) together with the
``get_permission`` / ``get_permission_scope`` lookups. The checks resolve a user's roles as
their own active assignments plus the assignments of any group they actively
belong to, both matched against the same scope chain.

These live in one module on purpose: the ``require*`` gate needs ``can`` while the
checks need the ``Permission`` class and the ``PERMISSIONS`` hook, so
splitting them forces the two modules to import each other at runtime — a cycle.
Assigning and revoking roles needs neither, so it lives in ``sparkth.core.permissions.grants``.

The public surface is re-exported from ``sparkth.lib.permissions`` — application code
and plugins import from there, never from this module directly.
"""

from collections.abc import Awaitable, Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import ColumnElement, and_, or_
from sqlalchemy.orm import Mapped
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.sql.expression import SelectOfScalar

from sparkth.core.models.user import User
from sparkth.core.permissions.exceptions import PermissionNotFound
from sparkth.core.permissions.models import (
    GroupMembership,
    GroupRoleAssignment,
    Role,
    RoleAssignment,
    RolePermission,
)
from sparkth.core.permissions.scopes import GLOBAL, PermissionScope
from sparkth.core.permissions.scopes.mixins import ScopeableMixin
from sparkth.lib.audit import record_event_now
from sparkth.lib.audit.events import AuditOutcome, AuditTarget, PermissionDeniedAuditEvent
from sparkth.lib.auth import get_current_user
from sparkth.lib.db import get_async_session
from sparkth.lib.hooks import SingleNamedItemHook
from sparkth.lib.i18n import _
from sparkth.lib.log import get_logger

logger = get_logger(__name__)


ObjectSource = Callable[..., Awaitable[tuple[str | None, str | None]]]
"""A FastAPI dependency yielding the checked object's ``(scope_object_id, scope_path)``."""


async def _no_object() -> tuple[str | None, str | None]:
    """The object source of an objectless scope: no id and no path."""
    return None, None


def _path_param_source(scope_param: str) -> ObjectSource:
    """An object source reading the id from the route's ``scope_param`` path parameter."""

    async def source(request: Request) -> tuple[str | None, str | None]:
        if scope_param not in request.path_params:
            logger.error(
                "Permission dependency misconfigured: scope_param %r is not among the route's path params %s",
                scope_param,
                list(request.path_params),
            )
            raise RuntimeError("Permission scope is misconfigured")
        return request.path_params[scope_param], None

    return source


def _fixed_source(object_id: str) -> ObjectSource:
    """An object source returning the fixed ``object_id``."""

    async def source() -> tuple[str | None, str | None]:
        return object_id, None

    return source


def _dependency_source(object_id: Callable[..., Awaitable[str | ScopeableMixin]]) -> ObjectSource:
    """An object source wrapping the ``object_id`` dependency, which returns an id or a record."""

    async def source(resolved: str | ScopeableMixin = Depends(object_id)) -> tuple[str | None, str | None]:
        if isinstance(resolved, str):
            return resolved, None
        return resolved.scope_id, resolved.scope_path

    return source


def _object_source(
    scope_param: str | None, object_id: str | Callable[..., Awaitable[str | ScopeableMixin]] | None
) -> ObjectSource:
    """Pick the object source for a route: the path parameter, the fixed id, the dependency, or none."""
    if scope_param is not None:
        return _path_param_source(scope_param)
    if isinstance(object_id, str):
        return _fixed_source(object_id)
    if object_id is not None:
        return _dependency_source(object_id)
    return _no_object


class Permission:
    def __init__(self, name: str) -> None:
        self.name = name

    @classmethod
    def create(cls, name: str) -> "Permission":
        """Create a permission and register it on the PERMISSIONS hook.

        Use this, not the bare ``Permission(name)`` constructor — the constructor does not
        register (it is internal/test-only), and an unregistered permission authorizes nothing.
        """
        permission = cls(name)
        PERMISSIONS.add_item(permission)
        return permission

    def _require_permission(
        self, permission_scope: PermissionScope, object_source: ObjectSource
    ) -> Callable[..., Awaitable[User]]:
        """Build the FastAPI dependency enforcing this permission at ``permission_scope``.

        Shared by ``require`` and ``require_in_global_scope``. FastAPI cannot inject the scope or
        ``object_source`` (they are fixed when the route is declared, not per request), so this
        returns a closure that captures them and declares only the sub-dependencies FastAPI does
        resolve: the current user, the DB session, then ``object_source``. The user comes first,
        so an unauthenticated request is refused with 401 before any object lookup runs.

        ``object_source`` yields ``(scope_object_id, scope_path)`` for the checked object. The
        dependency returns the authenticated ``User`` on success; a failed permission check
        raises 403.

        Before raising the 403 the refusal is recorded as a ``permission.denied`` audit event
        in its own transaction (``record_event_now``), so it survives the request's rollback.
        The write is fail-closed: if it fails, the error propagates and the request fails
        instead of returning 403.
        """

        async def dependency(
            current_user: User = Depends(get_current_user),
            session: AsyncSession = Depends(get_async_session),
            source: tuple[str | None, str | None] = Depends(object_source),
        ) -> User:
            scope_object_id, scope_path = source
            if not await can(current_user, self, permission_scope, scope_object_id, session, scope_path):
                scope_detail = f"scope={permission_scope.name}"
                if scope_object_id is not None:
                    scope_detail += f":{scope_object_id}"
                await record_event_now(
                    PermissionDeniedAuditEvent(
                        outcome=AuditOutcome.DENIED,
                        target=AuditTarget(type="permission", id=self.name),
                        error_detail=scope_detail,
                    )
                )
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_("Permission denied"))
            return current_user

        return dependency

    def require_in_global_scope(self) -> Callable[..., Awaitable[User]]:
        """Return a FastAPI dependency enforcing this permission at the GLOBAL scope.

        The dependency resolves the current user, checks the permission with no scope object
        id, returns the authenticated ``User`` on success, and raises 403 otherwise.
        """
        return self._require_permission(GLOBAL, _no_object)

    def require(
        self,
        permission_scope: PermissionScope,
        scope_param: str | None = None,
        object_id: str | Callable[..., Awaitable[str | ScopeableMixin]] | None = None,
    ) -> Callable[..., Awaitable[User]]:
        """Return a FastAPI dependency enforcing this permission at a scope.

        Args:
            permission_scope: The scope to check at, as a declared ``PermissionScope`` object
                (e.g. ``GLOBAL``, ``WHITELIST``, your ``COURSE``). Pass the registered instance,
                not its name — this keeps scope references object-based, like the RBAC engine
                functions, so a typo is an import error rather than a silent lookup miss.
            scope_param: The route path parameter carrying the scope object id, resolved from
                ``request.path_params`` per request. A ``scope_param`` the route does not provide
                raises 500 (a wiring error, never a silent 403).
            object_id: Another source for the scope object id: a fixed id string, or an async
                FastAPI dependency returning the id as a ``str`` or a ``ScopeableMixin`` record. For a
                record, its ``scope_path`` is passed to the check, so a role granted at an
                ancestor object authorizes it too. The dependency loads the record itself and
                raises its own not-found error when it is missing, which runs after
                authentication and before the permission check.

        An objectless scope takes neither ``scope_param`` nor ``object_id``; an object-bearing
        scope takes exactly one of them. Any other combination is a wiring error and raises
        ``ValueError`` at definition time.
        """
        permission_scope.validate_object_source(scope_param, object_id)
        return self._require_permission(permission_scope, _object_source(scope_param, object_id))


# Every permission the platform knows; Permission.create() registers each one here.
# This hook is the single source of truth — get_permission() resolves names against it.
PERMISSIONS: SingleNamedItemHook[Permission] = SingleNamedItemHook()


def get_permission(name: str) -> Permission:
    """Return the registered permission named ``name``, or raise PermissionNotFound."""
    permission = PERMISSIONS.get(name)
    if permission is None:
        raise PermissionNotFound(name)
    return permission


# Core Permissions shipped with the application.

# The email-whitelist permissions gate the registration email whitelist.
EMAIL_WHITELIST_READ = Permission.create("email.whitelist.read")
EMAIL_WHITELIST_CREATE = Permission.create("email.whitelist.create")
EMAIL_WHITELIST_DELETE = Permission.create("email.whitelist.delete")

# The role-management permissions gate the role-management API (sparkth/api/v1/permissions).
ROLE_CREATE = Permission.create("role.create")
ROLE_READ = Permission.create("role.read")
ROLE_UPDATE = Permission.create("role.update")
ROLE_DELETE = Permission.create("role.delete")

# The group-management permissions gate the group-management API (sparkth/api/v1/permissions).
# Membership and group-role grants are CLI-managed and carry no REST gate of their own.
GROUP_CREATE = Permission.create("group.create")
GROUP_READ = Permission.create("group.read")
GROUP_UPDATE = Permission.create("group.update")
GROUP_DELETE = Permission.create("group.delete")

# Reading the permission vocabulary itself (the assignable-permissions listing), distinct from
# reading roles.
PERMISSION_READ = Permission.create("permission.read")

# The analytics read permission gates the in-app analytics dashboards / read API.
ANALYTICS_READ = Permission.create("analytics.read")

# The audit read permission gates querying and exporting the audit trail.
AUDIT_READ = Permission.create("audit.read")

# Reading user identities (usernames) outside user management, e.g. actor names in analytics.
USER_READ = Permission.create("user.read")


def _scope_clause(
    scope_column: Mapped[str],
    object_id_column: Mapped[str | None],
    pairs: list[tuple[str, str | None]],
) -> ColumnElement[bool]:
    """WHERE clause matching an assignment table's (scope, object id) columns against ``pairs``,
    the ``(scope name, object id)`` pairs a grant may occupy to satisfy a check.

    The pairs are the checked scope and object, each
    ancestor object named by the check's scope path, and each objectless ancestor.

    Read-side only (``can`` / ``has_role``). The write operations (``assign_role``,
    ``revoke_role``) target the exact assignment row and must NOT use this — they never
    cascade to ancestor scopes.
    """
    return or_(*(and_(scope_column == name, object_id_column == object_id) for name, object_id in pairs))


def _user_role_ids_at_scope(user_id: int | None, pairs: list[tuple[str, str | None]]) -> SelectOfScalar[int]:
    """Subquery of role ids the user holds via their own active assignments at any of ``pairs``."""
    return select(RoleAssignment.role_id).where(
        col(RoleAssignment.user_id) == user_id,
        col(RoleAssignment.is_deleted) == False,
        _scope_clause(col(RoleAssignment.scope), col(RoleAssignment.scope_object_id), pairs),
    )


def _group_role_ids_at_scope(user_id: int | None, pairs: list[tuple[str, str | None]]) -> SelectOfScalar[int]:
    """Subquery of role ids granted at any of ``pairs`` to a group the user actively belongs to."""
    active_membership_group_ids = select(GroupMembership.group_id).where(
        col(GroupMembership.user_id) == user_id,
        col(GroupMembership.is_deleted) == False,
    )
    return select(GroupRoleAssignment.role_id).where(
        col(GroupRoleAssignment.group_id).in_(active_membership_group_ids),
        col(GroupRoleAssignment.is_deleted) == False,
        _scope_clause(col(GroupRoleAssignment.scope), col(GroupRoleAssignment.scope_object_id), pairs),
    )


def _granted_role_ids_clause(
    role_id_column: Mapped[int] | Mapped[int | None],
    user_id: int | None,
    pairs: list[tuple[str, str | None]],
) -> ColumnElement[bool]:
    """Whether ``role_id_column`` is a role the user holds at any of ``pairs`` — via their own
    assignments or via an assignment to a group they actively belong to."""
    return or_(
        role_id_column.in_(_user_role_ids_at_scope(user_id, pairs)),
        role_id_column.in_(_group_role_ids_at_scope(user_id, pairs)),
    )


async def can(
    user: User,
    permission: Permission,
    permission_scope: PermissionScope,
    scope_object_id: str | None,
    session: AsyncSession,
    scope_path: str | None = None,
) -> bool:
    """Return whether user holds permission at the given permission scope.

    ``scope_path`` is the materialized path of the checked object; when given, a grant at any
    ancestor object on the path also authorizes. Without it, only the scope itself and its
    objectless ancestors do.
    """
    pairs = permission_scope.scope_chain(scope_object_id, scope_path)
    statement = (
        select(RolePermission.permission)
        .where(
            RolePermission.permission == permission.name,
            _granted_role_ids_clause(col(RolePermission.role_id), user.id, pairs),
        )
        .limit(1)
    )
    result = await session.exec(statement)
    return result.first() is not None


async def has_role(
    user: User,
    role_name: str,
    permission_scope: PermissionScope,
    scope_object_id: str | None,
    session: AsyncSession,
    scope_path: str | None = None,
) -> bool:
    """Return whether user holds an active assignment of role_name at the given permission scope.

    A ``scope_path``, the materialized path of the checked object, also lets a role granted at
    an ancestor object count.
    """
    pairs = permission_scope.scope_chain(scope_object_id, scope_path)
    statement = (
        select(Role.id)
        .where(
            Role.name == role_name,
            _granted_role_ids_clause(col(Role.id), user.id, pairs),
        )
        .limit(1)
    )
    result = await session.exec(statement)
    return result.first() is not None
