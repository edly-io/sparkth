"""Public API for the permissions framework.

Application code and plugins import the permissions surface from here, never from
``sparkth.core.permissions`` or the hook modules directly. A plugin declares its
permissions and scope kinds from its ``__init__`` with ``Permission.create()`` and
``PermissionScope.create()`` (or ``ObjectlessPermissionScope.create()`` for a singleton scope)::

    from sparkth.lib.permissions import Permission
    from sparkth.lib.permissions.scopes import GLOBAL, PermissionScope

    PermissionScope.create("course", parent=GLOBAL)
    Permission.create("course.grade")
"""

from sparkth.core.permissions import (
    ANALYTICS_READ,
    EMAIL_WHITELIST_CREATE,
    EMAIL_WHITELIST_DELETE,
    EMAIL_WHITELIST_READ,
    PERMISSION_READ,
    ROLE_CREATE,
    ROLE_DELETE,
    ROLE_READ,
    ROLE_UPDATE,
    Permission,
    assign_role,
    can,
    get_permission,
    get_user_permissions,
    has_role,
    revoke_role,
)
from sparkth.core.permissions.scopes import get_permission_scope

__all__ = [
    "assign_role",
    "can",
    "get_permission",
    "get_permission_scope",
    "get_user_permissions",
    "has_role",
    "revoke_role",
    "Permission",
    "EMAIL_WHITELIST_READ",
    "EMAIL_WHITELIST_CREATE",
    "EMAIL_WHITELIST_DELETE",
    "ROLE_CREATE",
    "ROLE_READ",
    "ROLE_UPDATE",
    "ROLE_DELETE",
    "PERMISSION_READ",
    "ANALYTICS_READ",
]
