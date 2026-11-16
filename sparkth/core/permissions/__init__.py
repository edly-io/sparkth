"""Core scoped-RBAC permissions: the vocabulary and the FastAPI gate.

Holds the :class:`Permission` class and the ``PERMISSIONS`` hook (the permission
vocabulary), the shipped core permissions, the ``Permission.require*`` FastAPI
dependency layer, and the ``get_permission`` / ``get_permission_scope`` lookups. The gate
asks the read-side engine whether a user holds a permission. Assigning and revoking roles
lives apart from this module.

The public surface is re-exported from ``sparkth.lib.permissions`` — application code
and plugins import from there, never from this module directly.
"""

from collections.abc import Awaitable, Callable
from typing import NoReturn

from fastapi import Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User
from sparkth.core.permissions.dependencies import build_scope_path_dependency
from sparkth.core.permissions.engine import can, get_accessible_scope_object_ids
from sparkth.core.permissions.exceptions import PermissionNotFound
from sparkth.core.permissions.scopes import GLOBAL, PermissionScope
from sparkth.core.permissions.scopes.mixins import ScopeObjectMixin
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
        scope_object_id: str | Callable[..., Awaitable[str | int | ScopeObjectMixin | None]] | None,
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
        in its own transaction, so it survives the request's rollback.
        The write is fail-closed: if it fails, the error propagates and the request fails
        instead of returning 403.
        """

        async def dependency(
            current_user: User = Depends(get_current_user),
            session: AsyncSession = Depends(get_async_session),
            scope_path: str | None = Depends(
                build_scope_path_dependency(permission_scope, scope_param, scope_object_id)
            ),
        ) -> User:
            if not await can(current_user, self, permission_scope, scope_path, session):
                await self._deny(_describe_checked_scope(permission_scope, scope_path))
            return current_user

        return dependency

    async def _deny(self, scope_detail: str) -> NoReturn:
        """Record the refusal as a ``permission.denied`` audit event, then raise 403.

        The event is written in its own transaction, so it survives the request's rollback. The
        write is fail-closed: if it fails, the error propagates and the request fails instead of
        returning 403.
        """
        await record_event_now(
            PermissionDeniedAuditEvent(
                outcome=AuditOutcome.DENIED,
                target=AuditTarget(type="permission", id=self.name),
                error_detail=scope_detail,
            )
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_("Permission denied"))

    def require_for_any_object(self, permission_scope: PermissionScope) -> Callable[..., Awaitable[set[str] | None]]:
        """Return a FastAPI dependency for a route that names no object, such as a list route.

        The dependency returns the ids of the ``permission_scope`` objects at which the caller holds
        this permission, or ``None`` when a grant at an objectless ancestor covers every object. A
        caller who holds it at no object is refused with 403 and a ``permission.denied`` audit
        event. The route filters its query by the returned ids.

        An objectless scope names no objects to list, so passing one raises ``ValueError`` at
        definition time.

        Returns:
            The ids of the objects the caller holds the permission at, or ``None`` when a grant at an
            objectless ancestor covers every object. A caller who holds it nowhere is refused with
            403, so the route never receives an empty set.
        """
        permission_scope.validate_listable()

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
        self, permission_scope: PermissionScope, scope_param: str | None = None
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

        An objectless scope takes no ``scope_param``; an object-bearing scope needs one. Any other
        combination is a wiring error and raises ``ValueError`` at definition time. A route whose
        object does not come from a path parameter uses :meth:`require_for_object`.
        """
        permission_scope.validate_names_object(scope_param is not None)
        return self._require_permission(permission_scope, scope_param, None)

    def require_for_object(
        self,
        permission_scope: PermissionScope,
        scope_object_id: str | Callable[..., Awaitable[str | int | ScopeObjectMixin | None]],
    ) -> Callable[..., Awaitable[User]]:
        """Return a FastAPI dependency enforcing this permission at one object of a scope.

        Args:
            permission_scope: The object-bearing scope to check at. An objectless scope raises
                ``ValueError`` at definition time.
            scope_object_id: A fixed id string, or an async FastAPI dependency returning the id as a
                ``str`` or ``int``, a ``ScopeObjectMixin`` record, or ``None`` when the object does not exist.
                For a record, its ``scope_path`` is passed to the check, so a role granted at an
                ancestor object authorizes it too. ``None`` is checked at the scope itself, so a
                caller holding the permission only at objects is refused with 403 and cannot tell a
                missing object from one they may not access; the route then raises its own
                not-found after the check passes. The dependency runs after authentication and
                before the permission check.
        """
        permission_scope.validate_names_object(True)
        return self._require_permission(permission_scope, None, scope_object_id)


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

# LLM provider configurations, each checked at the user scope of the config's owner.
LLM_CONFIG_CREATE = Permission.create("llm.config.create")
LLM_CONFIG_READ = Permission.create("llm.config.read")
LLM_CONFIG_UPDATE = Permission.create("llm.config.update")
LLM_CONFIG_DELETE = Permission.create("llm.config.delete")
