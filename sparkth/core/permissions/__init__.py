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
from typing import NoReturn

from fastapi import Depends, HTTPException, status
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
from sparkth.core.permissions.scopes import GLOBAL, ObjectlessPermissionScope, PermissionScope
from sparkth.core.permissions.scopes.mixins import ScopeObjectMixin
from sparkth.core.permissions.utils import get_scope_path
from sparkth.lib.audit import record_event_now
from sparkth.lib.audit.events import AuditOutcome, AuditTarget, PermissionDeniedAuditEvent
from sparkth.lib.auth import get_current_user
from sparkth.lib.db import get_async_session
from sparkth.lib.hooks import SingleNamedItemHook
from sparkth.lib.i18n import _


def _describe_checked_scope(permission_scope: PermissionScope, scope_path: str | None) -> str:
    """Name the checked scope for a denial record: ``scope=<name>``, then ``:<object id>`` when it has one."""
    name, object_id = permission_scope.scope_chain(scope_path)[0]
    return f"scope={name}" if object_id is None else f"scope={name}:{object_id}"


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
        self,
        permission_scope: PermissionScope,
        scope_param: str | None,
        scope_object_id: str | Callable[..., Awaitable[str | ScopeObjectMixin]] | None,
    ) -> Callable[..., Awaitable[User]]:
        """Build the FastAPI dependency enforcing this permission at ``permission_scope``.

        Shared by ``require`` and ``require_in_global_scope``. FastAPI cannot inject the scope,
        ``scope_param`` or ``scope_object_id`` (they are fixed when the route is declared, not per
        request), so this returns a closure that captures them and declares only the
        sub-dependencies FastAPI does resolve: the current user, the DB session, then the checked
        object's scope path. The user comes first, so an unauthenticated
        request is refused with 401 before any object lookup runs.

        The dependency returns the authenticated ``User`` on success; a failed permission check
        raises 403.

        Before raising the 403 the refusal is recorded as a ``permission.denied`` audit event
        in its own transaction (``record_event_now``), so it survives the request's rollback.
        The write is fail-closed: if it fails, the error propagates and the request fails
        instead of returning 403.
        """

        async def dependency(
            current_user: User = Depends(get_current_user),
            session: AsyncSession = Depends(get_async_session),
            scope_path: str | None = Depends(get_scope_path(permission_scope, scope_param, scope_object_id)),
        ) -> User:
            if not await can(current_user, self, permission_scope, scope_path, session):
                await self._deny(_describe_checked_scope(permission_scope, scope_path))
            return current_user

        return dependency

    async def _deny(self, scope_detail: str) -> NoReturn:
        """Record the refusal as a ``permission.denied`` audit event, then raise 403.

        The event is written in its own transaction (``record_event_now``), so it survives the
        request's rollback. The write is fail-closed: if it fails, the error propagates and the
        request fails instead of returning 403.
        """
        await record_event_now(
            PermissionDeniedAuditEvent(
                outcome=AuditOutcome.DENIED,
                target=AuditTarget(type="permission", id=self.name),
                error_detail=scope_detail,
            )
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_("Permission denied"))

    def require_accessible(self, permission_scope: PermissionScope) -> Callable[..., Awaitable[set[str] | None]]:
        """Return a FastAPI dependency for a route that names no object, such as a list route.

        The dependency returns the ids of the ``permission_scope`` objects at which the caller holds
        this permission, or ``None`` when a grant at an objectless ancestor covers every object. A
        caller who holds it at no object is refused with 403 and a ``permission.denied`` audit
        event. The route filters its query by the returned ids.

        An objectless scope names no objects to list, so passing one raises ``ValueError`` at
        definition time; use ``require_in_global_scope`` or ``require`` for it.

        Returns:
            - a set of ids: the caller has the permission on those objects only.
            - an empty set: the caller has no permission on any object, so the dependency raises 403
              and the route never sees it.
            - ``None``: the caller has access to all ids.
        """
        if isinstance(permission_scope, ObjectlessPermissionScope):
            raise ValueError(f"Scope {permission_scope.name!r} is objectless and names no objects to list")

        async def dependency(
            current_user: User = Depends(get_current_user),
            session: AsyncSession = Depends(get_async_session),
        ) -> set[str] | None:
            accessible_ids = await get_accessible_scope_object_ids(current_user, self, permission_scope, session)
            if accessible_ids is not None and not accessible_ids:
                await self._deny(_describe_checked_scope(permission_scope, None))
            return accessible_ids

        return dependency

    def require_in_global_scope(self) -> Callable[..., Awaitable[User]]:
        """Return a FastAPI dependency enforcing this permission at the GLOBAL scope.

        The dependency resolves the current user, checks the permission with no scope object
        id, returns the authenticated ``User`` on success, and raises 403 otherwise.
        """
        return self._require_permission(GLOBAL, None, None)

    def require(
        self,
        permission_scope: PermissionScope,
        scope_param: str | None = None,
        scope_object_id: str | Callable[..., Awaitable[str | ScopeObjectMixin]] | None = None,
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
            scope_object_id: The scope object id when the route has no path parameter for it: a fixed
                id string, or an async FastAPI dependency returning the id as a ``str`` or a
                ``ScopeObjectMixin`` record. For a record, its ``scope_path`` is passed to the
                check, so a role granted at an ancestor object authorizes it too. The dependency
                loads the record itself and raises its own not-found error when it is missing,
                which runs after authentication and before the permission check.

        An objectless scope takes neither ``scope_param`` nor ``scope_object_id``; an object-bearing
        scope takes exactly one of them. Any other combination is a wiring error and raises
        ``ValueError`` at definition time.
        """
        permission_scope.validate_scope_object_id_arguments(scope_param, scope_object_id)
        return self._require_permission(permission_scope, scope_param, scope_object_id)


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
    _scope_chain: list[tuple[str, str | None]],
) -> ColumnElement[bool]:
    """WHERE clause matching an assignment table's (scope, object id) columns against ``_scope_chain``,
    the ``(scope name, object id)`` pairs a grant may occupy to satisfy a check.

    The pairs are the checked scope and object, each
    ancestor object named by the check's scope path, and each objectless ancestor.

    Read-side only (``can`` / ``has_role``). The write operations (``assign_role``,
    ``revoke_role``) target the exact assignment row and must NOT use this — they never
    cascade to ancestor scopes.
    """
    return or_(*(and_(scope_column == name, object_id_column == object_id) for name, object_id in _scope_chain))


def _user_role_ids_at_scope(user_id: int | None, _scope_chain: list[tuple[str, str | None]]) -> SelectOfScalar[int]:
    """Subquery of role ids the user holds via their own active assignments at any of ``_scope_chain``."""
    return select(RoleAssignment.role_id).where(
        col(RoleAssignment.user_id) == user_id,
        col(RoleAssignment.is_deleted) == False,
        _scope_clause(col(RoleAssignment.scope), col(RoleAssignment.scope_object_id), _scope_chain),
    )


def _active_membership_group_ids(user_id: int | None) -> SelectOfScalar[int]:
    """Subquery of the ids of the groups the user actively belongs to."""
    return select(GroupMembership.group_id).where(
        col(GroupMembership.user_id) == user_id,
        col(GroupMembership.is_deleted) == False,
    )


def _group_role_ids_at_scope(user_id: int | None, _scope_chain: list[tuple[str, str | None]]) -> SelectOfScalar[int]:
    """Subquery of role ids granted at any of ``_scope_chain`` to a group the user actively belongs to."""
    return select(GroupRoleAssignment.role_id).where(
        col(GroupRoleAssignment.group_id).in_(_active_membership_group_ids(user_id)),
        col(GroupRoleAssignment.is_deleted) == False,
        _scope_clause(col(GroupRoleAssignment.scope), col(GroupRoleAssignment.scope_object_id), _scope_chain),
    )


def _granted_role_ids_clause(
    role_id_column: Mapped[int] | Mapped[int | None],
    user_id: int | None,
    _scope_chain: list[tuple[str, str | None]],
) -> ColumnElement[bool]:
    """Whether ``role_id_column`` is a role the user holds at any of ``_scope_chain`` — via their own
    assignments or via an assignment to a group they actively belong to."""
    return or_(
        role_id_column.in_(_user_role_ids_at_scope(user_id, _scope_chain)),
        role_id_column.in_(_group_role_ids_at_scope(user_id, _scope_chain)),
    )


async def can(
    user: User,
    permission: Permission,
    permission_scope: PermissionScope,
    scope_path: str | None,
    session: AsyncSession,
) -> bool:
    """Return whether user holds permission at the given permission scope.

    ``scope_path`` is the materialized path of the checked object; a grant at the object or at any
    ancestor object on the path authorizes. Without it, only the scope itself and its objectless
    ancestors do. Raises ``ValueError`` when the path's leaf names another scope.
    """
    _scope_chain = permission_scope.scope_chain(scope_path)
    statement = (
        select(RolePermission.permission)
        .where(
            RolePermission.permission == permission.name,
            _granted_role_ids_clause(col(RolePermission.role_id), user.id, _scope_chain),
        )
        .limit(1)
    )
    result = await session.exec(statement)
    return result.first() is not None


async def has_role(
    user: User,
    role_name: str,
    permission_scope: PermissionScope,
    scope_path: str | None,
    session: AsyncSession,
) -> bool:
    """Return whether user holds an active assignment of role_name at the given permission scope.

    ``scope_path`` is the materialized path of the checked object; a role granted at the object or
    at any ancestor object on the path counts. Raises ``ValueError`` when the path's leaf names
    another scope.
    """
    _scope_chain = permission_scope.scope_chain(scope_path)
    statement = (
        select(Role.id)
        .where(
            Role.name == role_name,
            _granted_role_ids_clause(col(Role.id), user.id, _scope_chain),
        )
        .limit(1)
    )
    result = await session.exec(statement)
    return result.first() is not None


def _reduce_grant_rows(grant_rows: list[tuple[str, str | None]], scope_name: str) -> set[str] | None:
    """Reduce the ``(scope, object id)`` rows of a user's grants to the ids they cover at ``scope_name``.

    A row at an objectless ancestor (NULL object id) covers every object, so it returns ``None``.
    """
    object_ids: set[str] = set()
    for scope, object_id in grant_rows:
        if scope != scope_name:
            if object_id is None:
                return None
        elif object_id is not None:
            object_ids.add(object_id)
    return object_ids


async def get_accessible_scope_object_ids(
    user: User,
    permission: Permission,
    permission_scope: PermissionScope,
    session: AsyncSession,
) -> set[str] | None:
    """Return the ids of the ``permission_scope`` objects at which ``user`` holds ``permission``.

    Grants come from the user's own active assignments and from active assignments of the groups
    they actively belong to. Returns ``None`` when a grant at an objectless ancestor (``global``)
    covers every object, otherwise the set of object ids, empty when the user holds the permission
    nowhere. Grants at an object-bearing ancestor are not considered.
    """
    scope_name = permission_scope.name
    scope_names = {name for name, _ in permission_scope.scope_chain(None)}
    roles_with_permission = select(RolePermission.role_id).where(RolePermission.permission == permission.name)
    own_grants = select(col(RoleAssignment.scope), col(RoleAssignment.scope_object_id)).where(
        col(RoleAssignment.user_id) == user.id,
        col(RoleAssignment.is_deleted) == False,
        col(RoleAssignment.role_id).in_(roles_with_permission),
        col(RoleAssignment.scope).in_(scope_names),
    )
    group_grants = select(col(GroupRoleAssignment.scope), col(GroupRoleAssignment.scope_object_id)).where(
        col(GroupRoleAssignment.group_id).in_(_active_membership_group_ids(user.id)),
        col(GroupRoleAssignment.is_deleted) == False,
        col(GroupRoleAssignment.role_id).in_(roles_with_permission),
        col(GroupRoleAssignment.scope).in_(scope_names),
    )
    grants = own_grants.union_all(group_grants).subquery()
    result = await session.exec(select(grants.c.scope, grants.c.scope_object_id))
    return _reduce_grant_rows([(scope, object_id) for scope, object_id in result.all()], scope_name)
