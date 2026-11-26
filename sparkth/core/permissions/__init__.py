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

from sparkth.core.i18n import gettext_noop
from sparkth.core.models.user import User
from sparkth.core.permissions.dependencies import build_scope_path_dependency
from sparkth.core.permissions.engine import can, get_accessible_scope_object_ids
from sparkth.core.permissions.enums import PermissionRisk
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
    """A permission a role can hold, and what it is for as people read it.

    ``label``, ``description`` and ``category`` are English marked for translation, translated when
    shown, and ``category`` groups related permissions. ``risks`` are the reasons to think twice before
    granting it, and ``requires`` holds the permissions a holder also needs for it to be of use; none
    is declared today, as the permission system has no hierarchy yet.
    """

    def __init__(
        self,
        name: str,
        label: str = "",
        description: str = "",
        category: str = "",
        risks: tuple[PermissionRisk, ...] = (),
        requires: tuple["Permission", ...] = (),
    ) -> None:
        self.name = name
        self.label = label
        self.description = description
        self.category = category
        self.risks = risks
        self.requires = requires

    @classmethod
    def create(
        cls,
        name: str,
        label: str,
        description: str,
        category: str,
        risks: tuple[PermissionRisk, ...] = (),
        requires: tuple["Permission", ...] = (),
    ) -> "Permission":
        """Create a permission, with what it is for, and register it on the PERMISSIONS hook.

        Use this, not the bare ``Permission(name)`` constructor — the constructor does not
        register (it is internal/test-only), and an unregistered permission authorizes nothing.
        """
        permission = cls(name, label, description, category, risks, requires)
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
                await self._deny(permission_scope, scope_path)
            return current_user

        return dependency

    async def record_denial(self, permission_scope: PermissionScope, scope_path: str | None) -> None:
        """Record a ``permission.denied`` audit event for this permission at the checked scope.

        The event is written in its own transaction, so it survives the caller's rollback. The
        write is fail-closed: if it fails, the error propagates.
        """
        await record_event_now(
            PermissionDeniedAuditEvent(
                outcome=AuditOutcome.DENIED,
                target=AuditTarget(type="permission", id=self.name),
                error_detail=_describe_checked_scope(permission_scope, scope_path),
            )
        )

    async def _deny(self, permission_scope: PermissionScope, scope_path: str | None) -> NoReturn:
        """Record the refusal as a ``permission.denied`` audit event, then raise 403.

        The write is fail-closed: if it fails, the error propagates and the request fails instead
        of returning 403.
        """
        await self.record_denial(permission_scope, scope_path)
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
                await self._deny(permission_scope, None)
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


# Core Permissions shipped with the application. Each says what it is for, under the category
# it is listed in.
_USERS_AND_ACCESS = gettext_noop("Users & access")
_REGISTRATION_WHITELIST = gettext_noop("Registration whitelist")
_ANALYTICS_AND_AUDIT = gettext_noop("Analytics & audit")
_AI_KEYS = gettext_noop("AI keys")
_PLUGINS_AND_FILES = gettext_noop("Plugins & files")

# The email-whitelist permissions gate the registration email whitelist.
EMAIL_WHITELIST_READ = Permission.create(
    "email.whitelist.read",
    gettext_noop("See the whitelist"),
    gettext_noop("View which emails and domains may sign up."),
    _REGISTRATION_WHITELIST,
)
EMAIL_WHITELIST_CREATE = Permission.create(
    "email.whitelist.create",
    gettext_noop("Add to the whitelist"),
    gettext_noop("Let a new email or domain sign up."),
    _REGISTRATION_WHITELIST,
)
EMAIL_WHITELIST_DELETE = Permission.create(
    "email.whitelist.delete",
    gettext_noop("Remove from the whitelist"),
    gettext_noop("Stop an email or domain from signing up."),
    _REGISTRATION_WHITELIST,
    risks=(PermissionRisk.DELETES,),
)

# The role-management permissions gate the role-management API (sparkth/api/v1/permissions).
ROLE_CREATE = Permission.create(
    "role.create",
    gettext_noop("Create roles"),
    gettext_noop("Add new roles."),
    _USERS_AND_ACCESS,
    risks=(PermissionRisk.DELEGATES_ACCESS,),
)
ROLE_READ = Permission.create(
    "role.read",
    gettext_noop("See roles"),
    gettext_noop("Open the list of roles and what each one allows."),
    _USERS_AND_ACCESS,
)
ROLE_UPDATE = Permission.create(
    "role.update",
    gettext_noop("Edit roles"),
    gettext_noop("Rename roles and change their permissions."),
    _USERS_AND_ACCESS,
    risks=(PermissionRisk.DELEGATES_ACCESS,),
)
ROLE_DELETE = Permission.create(
    "role.delete",
    gettext_noop("Delete roles"),
    gettext_noop("Delete custom roles and take them away from everyone."),
    _USERS_AND_ACCESS,
    risks=(PermissionRisk.DELETES,),
)

# The group-management permissions gate the group-management API (sparkth/api/v1/permissions).
# Membership and group-role grants are CLI-managed and carry no REST gate of their own.
GROUP_CREATE = Permission.create(
    "group.create",
    gettext_noop("Create groups"),
    gettext_noop("Add new groups."),
    _USERS_AND_ACCESS,
)
GROUP_READ = Permission.create(
    "group.read",
    gettext_noop("See groups"),
    gettext_noop("Open groups and their members."),
    _USERS_AND_ACCESS,
)
GROUP_UPDATE = Permission.create(
    "group.update",
    gettext_noop("Edit groups"),
    gettext_noop("Rename groups and change their description."),
    _USERS_AND_ACCESS,
    risks=(PermissionRisk.DELEGATES_ACCESS,),
)
GROUP_DELETE = Permission.create(
    "group.delete",
    gettext_noop("Delete groups"),
    gettext_noop("Delete groups and take their roles away from their members."),
    _USERS_AND_ACCESS,
    risks=(PermissionRisk.DELETES,),
)

# Reading the permission vocabulary itself (the assignable-permissions listing), distinct from
# reading roles.
PERMISSION_READ = Permission.create(
    "permission.read",
    gettext_noop("See permissions"),
    gettext_noop("List the permissions a role can hold."),
    _USERS_AND_ACCESS,
)

# The analytics read permission gates the in-app analytics dashboards / read API.
ANALYTICS_READ = Permission.create(
    "analytics.read",
    gettext_noop("View analytics"),
    gettext_noop("Open the analytics dashboards and run Explore queries."),
    _ANALYTICS_AND_AUDIT,
)

# The audit read permission gates querying and exporting the audit trail.
AUDIT_READ = Permission.create(
    "audit.read",
    gettext_noop("View the audit log"),
    gettext_noop("Read and export the record of every access change."),
    _ANALYTICS_AND_AUDIT,
    risks=(PermissionRisk.PRIVATE_DATA,),
)

# Reading user identities: actor names in analytics (Explore and its saved views), and listing and
# reading users with their email addresses through the users API.
USER_READ = Permission.create(
    "user.read",
    gettext_noop("See information about users"),
    gettext_noop("List the people in Sparkth with their email addresses, and see who did what in analytics."),
    _USERS_AND_ACCESS,
    risks=(PermissionRisk.PRIVATE_DATA,),
)

# LLM provider configurations, each checked at the user scope of the config's owner.
LLM_CONFIG_CREATE = Permission.create(
    "llm.config.create",
    gettext_noop("Add AI keys"),
    gettext_noop("Save a new AI provider and key."),
    _AI_KEYS,
)
LLM_CONFIG_READ = Permission.create(
    "llm.config.read",
    gettext_noop("See AI key settings"),
    gettext_noop("View saved AI providers and models."),
    _AI_KEYS,
)
LLM_CONFIG_UPDATE = Permission.create(
    "llm.config.update",
    gettext_noop("Change AI keys"),
    gettext_noop("Edit, rotate or switch the active AI key."),
    _AI_KEYS,
)
LLM_CONFIG_DELETE = Permission.create(
    "llm.config.delete",
    gettext_noop("Delete AI keys"),
    gettext_noop("Remove saved AI keys."),
    _AI_KEYS,
)

# Using a plugin's feature routes, checked at the plugin scope of the plugin's name.
PLUGIN_USE = Permission.create(
    "plugin.use",
    gettext_noop("Use plugins"),
    gettext_noop("Use a plugin's features, such as Compose or Google Drive."),
    _PLUGINS_AND_FILES,
)

# Uploading files, checked at the user scope of the uploader.
FILE_UPLOAD = Permission.create(
    "file.upload",
    gettext_noop("Upload files"),
    gettext_noop("Upload files to read in conversations."),
    _PLUGINS_AND_FILES,
)
