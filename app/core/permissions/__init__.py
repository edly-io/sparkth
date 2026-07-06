"""Core scoped-RBAC permissions: the vocabulary, the FastAPI gate, and the engine.

Holds the :class:`Permission` class and the ``PERMISSIONS`` hook (the permission
vocabulary), the shipped core permissions, the ``Permission.require*`` FastAPI
dependency layer, and the RBAC engine functions (``can``, ``has_role``,
``assign_role``, ``revoke_role``) together with the ``get_permission`` /
``get_permission_scope`` lookups.

These live in one module on purpose: the ``require*`` gate needs ``can`` while the
engine functions need the ``Permission`` class and the ``PERMISSIONS`` hook, so
splitting them forces the two modules to import each other at runtime — a cycle.

The public surface is re-exported from ``app.lib.permissions`` — application code
and plugins import from there, never from this module directly.
"""

from collections.abc import Awaitable, Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import ColumnElement, and_, or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.permissions.exceptions import InvalidScopeObjectId, PermissionNotFound, RoleNotFound
from app.core.permissions.models import Role, RoleAssignment, RolePermission
from app.core.permissions.scopes import GLOBAL, PermissionScope, get_permission_scope
from app.lib.auth import get_current_user
from app.lib.db import get_async_session
from app.lib.hooks import SingleNamedItemHook
from app.lib.log import get_logger
from app.models.user import User

logger = get_logger(__name__)


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
        self, permission_scope: PermissionScope, scope_param: str | None
    ) -> Callable[..., Awaitable[User]]:
        """Build the FastAPI dependency enforcing this permission at ``permission_scope``.

        Shared by ``require`` and ``require_in_global_scope``. FastAPI cannot inject the scope or
        ``scope_param`` (they are fixed when the route is declared, not per request), so this
        returns a closure that captures them and declares only the sub-dependencies FastAPI does
        resolve (the current user and the DB session).

        The dependency returns the authenticated ``User`` on success. ``scope_param``, when set,
        names the path parameter carrying the scope object id, resolved from
        ``request.path_params`` per request; a ``scope_param`` the route does not provide raises
        500 (a wiring error, never a silent 403), and a failed permission check raises 403.
        """

        async def dependency(
            request: Request,
            current_user: User = Depends(get_current_user),
            session: AsyncSession = Depends(get_async_session),
        ) -> User:
            if scope_param is not None and scope_param not in request.path_params:
                logger.error(
                    "Permission dependency misconfigured: scope_param %r is not among the route's path params %s",
                    scope_param,
                    list(request.path_params),
                )
                raise RuntimeError("Permission scope is misconfigured")
            scope_object_id = request.path_params.get(scope_param) if scope_param else None
            if not await can(current_user, self, permission_scope, scope_object_id, session):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
            return current_user

        return dependency

    def require_in_global_scope(self) -> Callable[..., Awaitable[User]]:
        """Return a FastAPI dependency enforcing this permission at the GLOBAL scope.

        The dependency resolves the current user, checks the permission with no scope object
        id, returns the authenticated ``User`` on success, and raises 403 otherwise.
        """
        return self._require_permission(GLOBAL, None)

    def require(self, permission_scope: str, scope_param: str) -> Callable[..., Awaitable[User]]:
        """Return a FastAPI dependency enforcing this permission at a named scope.

        Args:
            permission_scope: A registered scope kind's name (e.g. ``"course"``). Resolved via
                ``get_permission_scope``; an unregistered name raises ``PermissionScopeNotFound``
                here (at route-definition/import time) so misconfiguration fails fast at startup.
            scope_param: The name of the route's path parameter carrying the scope object id;
                resolved from ``request.path_params`` on each request.
        """
        scope = get_permission_scope(permission_scope)
        return self._require_permission(scope, scope_param)


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

# The role-management permissions gate the role-management API (app/api/v1/permissions).
ROLE_CREATE = Permission.create("role.create")
ROLE_READ = Permission.create("role.read")
ROLE_UPDATE = Permission.create("role.update")
ROLE_DELETE = Permission.create("role.delete")

# Reading the permission vocabulary itself (the assignable-permissions listing), distinct from
# reading roles.
PERMISSION_READ = Permission.create("permission.read")


def _active_assignment_at_scope(
    user_id: int | None,
    permission_scope: PermissionScope,
    scope_object_id: str | None,
) -> tuple[ColumnElement[bool], ...]:
    """WHERE clauses selecting a user's active assignments that satisfy a check at one scope,
    honouring the scope hierarchy.

    A grant at the checked scope itself, or at any *objectless* ancestor, satisfies the check
    (parent -> child cascade). Objectless ancestors (``global``, ``whitelist``) name no object,
    so their id in the chain is NULL and is resolvable here. An object-bearing ancestor (e.g.
    ``course`` under an ``org``) would need a materialized path to resolve its id, so it is not
    walked yet (deferred; see issue #420 Phase 2).

    Shared by the read-side checks (``can`` and ``has_role``). The write operations
    (``assign_role``, ``revoke_role``) target the exact assignment row and must NOT use this —
    they never cascade to ancestor scopes.
    """
    scope_pairs: list[tuple[str, str | None]] = [(permission_scope.name, scope_object_id)]
    for ancestor in permission_scope.get_parents():
        if ancestor.objectless:
            scope_pairs.append((ancestor.name, None))
    scope_clause = or_(
        *(
            and_(
                col(RoleAssignment.scope) == name,
                col(RoleAssignment.scope_object_id) == object_id,
            )
            for name, object_id in scope_pairs
        )
    )
    return (
        col(RoleAssignment.user_id) == user_id,
        col(RoleAssignment.is_deleted) == False,
        scope_clause,
    )


async def _find_active_assignment(
    user_id: int,
    role_id: int,
    permission_scope: PermissionScope,
    scope_object_id: str | None,
    session: AsyncSession,
) -> RoleAssignment | None:
    """Return the user's active assignment of role_id at the exact scope, or None."""
    statement = (
        select(RoleAssignment)
        .where(
            RoleAssignment.user_id == user_id,
            RoleAssignment.role_id == role_id,
            RoleAssignment.scope == permission_scope.name,
            RoleAssignment.scope_object_id == scope_object_id,
            RoleAssignment.is_deleted == False,
        )
        .limit(1)
    )
    return (await session.exec(statement)).first()


async def can(
    user: User,
    permission: Permission,
    permission_scope: PermissionScope,
    scope_object_id: str | None,
    session: AsyncSession,
) -> bool:
    """Return whether user holds permission at the given permission scope."""
    statement = (
        select(RolePermission.permission)
        .join(RoleAssignment, col(RoleAssignment.role_id) == col(RolePermission.role_id))
        .where(
            *_active_assignment_at_scope(user.id, permission_scope, scope_object_id),
            RolePermission.permission == permission.name,
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
) -> bool:
    """Return whether user holds an active assignment of role_name at the given permission scope."""
    statement = (
        select(RoleAssignment.id)
        .join(Role, col(Role.id) == col(RoleAssignment.role_id))
        .where(
            *_active_assignment_at_scope(user.id, permission_scope, scope_object_id),
            Role.name == role_name,
        )
        .limit(1)
    )
    result = await session.exec(statement)
    return result.first() is not None


def _validate_scope_object_id(permission_scope: PermissionScope, scope_object_id: str | None) -> None:
    """Enforce the (scope, object id) pairing (replaces the former DB CHECK).

    Objectless scopes name no object; object-bearing scopes must. Raises InvalidScopeObjectId
    on a mismatch. The database no longer enforces this — the scope vocabulary lives in code.
    """
    if permission_scope.objectless and scope_object_id is not None:
        logger.error("Objectless scope %r was given object id %r", permission_scope.name, scope_object_id)
        raise InvalidScopeObjectId(permission_scope.name, scope_object_id)
    if not permission_scope.objectless and scope_object_id is None:
        logger.error("Object-bearing scope %r requires an object id", permission_scope.name)
        raise InvalidScopeObjectId(permission_scope.name, scope_object_id)


async def assign_role(
    user_id: int,
    role_name: str,
    permission_scope: PermissionScope,
    scope_object_id: str | None,
    session: AsyncSession,
) -> RoleAssignment:
    """Return the active assignment of role_name to user_id at the given permission scope, creating it if absent.

    Idempotent and race-safe: if a concurrent assign inserts the same (user, role, scope)
    between the existence check and our insert, the unique index rejects ours; we recover by
    re-querying and returning the winner instead of surfacing the IntegrityError.

    Raises RoleNotFound if the role does not exist. Raises InvalidScopeObjectId if the
    (permission_scope, scope_object_id) pairing is invalid (see _validate_scope_object_id).
    """
    _validate_scope_object_id(permission_scope, scope_object_id)
    role = (await session.exec(select(Role).where(Role.name == role_name))).one_or_none()
    if role is None or role.id is None:
        raise RoleNotFound(role_name)
    existing = await _find_active_assignment(user_id, role.id, permission_scope, scope_object_id, session)
    if existing is not None:
        return existing
    try:
        # Insert inside a savepoint so a unique-index violation rolls back cleanly without
        # poisoning the surrounding transaction.
        async with session.begin_nested():
            assignment = RoleAssignment(
                user_id=user_id, role_id=role.id, scope=permission_scope.name, scope_object_id=scope_object_id
            )
            session.add(assignment)
            await session.flush()
        return assignment
    except IntegrityError:
        # A concurrent assign_role inserted the same (user, role, scope) after our check, so
        # the unique index rejected ours. Re-query and return that winner to stay idempotent;
        # if it's somehow still not visible, re-raise.
        winner = await _find_active_assignment(user_id, role.id, permission_scope, scope_object_id, session)
        if winner is None:
            raise
        return winner


async def revoke_role(
    user_id: int,
    role_name: str,
    permission_scope: PermissionScope,
    scope_object_id: str | None,
    session: AsyncSession,
) -> None:
    """Soft-delete all active assignments of role_name for user_id at the given permission scope."""
    statement = (
        select(RoleAssignment)
        .join(Role, col(Role.id) == col(RoleAssignment.role_id))
        .where(
            RoleAssignment.user_id == user_id,
            Role.name == role_name,
            RoleAssignment.scope == permission_scope.name,
            RoleAssignment.scope_object_id == scope_object_id,
            RoleAssignment.is_deleted == False,
        )
    )
    assignments = (await session.exec(statement)).all()
    for assignment in assignments:
        # Already tracked by the session (they came from this query), so mutating them marks
        # them dirty — no session.add needed.
        assignment.soft_delete()
    await session.flush()
