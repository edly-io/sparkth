"""Public API for the permissions framework.

Application code and plugins import the permissions surface from here, never from
``app.core.permissions`` or the hook modules directly. A plugin declares its
permissions and scope kinds from its ``__init__`` with ``Permission.create()`` /
``PermissionScope.create()``::

    from app.lib.permissions import Permission
    from app.lib.permissions.scopes import GLOBAL, PermissionScope

    PermissionScope.create("course", parent=GLOBAL)
    Permission.create("course.grade")
"""

from app.core.permissions import (
    EMAIL_WHITELIST_CREATE,
    EMAIL_WHITELIST_DELETE,
    EMAIL_WHITELIST_READ,
    Permission,
)
from app.core.permissions.exceptions import PermissionNotFound, PermissionScopeNotFound, RoleNotFound
from app.core.permissions.utils import (
    assign_role,
    can,
    get_permission,
    get_permission_scope,
    has_role,
    revoke_role,
)

__all__ = [
    "assign_role",
    "can",
    "get_permission",
    "get_permission_scope",
    "has_role",
    "revoke_role",
    "Permission",
    "RoleNotFound",
    "PermissionNotFound",
    "PermissionScopeNotFound",
    "EMAIL_WHITELIST_READ",
    "EMAIL_WHITELIST_CREATE",
    "EMAIL_WHITELIST_DELETE",
]
