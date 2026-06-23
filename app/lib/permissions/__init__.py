"""Public API for the permissions framework.

Application code and plugins import the permissions surface from here, never from
``app.core.permissions`` or the hook modules directly. A plugin declares its
permissions and scope kinds from its ``__init__`` by adding them to the hooks::

    from app.lib.permissions import PERMISSIONS, PERMISSION_SCOPE, PermissionScope

    PERMISSION_SCOPE.add_item(self, PermissionScope("course", parent=...))
    PERMISSIONS.add_item(self, "course.grade")
"""

from app.core.permissions import assign_role, can, revoke_role
from app.core.permissions.exceptions import RoleNotFound
from app.core.permissions.scope import PermissionScope
from app.lib.permissions.hooks import PERMISSION_SCOPE, PERMISSIONS

__all__ = [
    "assign_role",
    "can",
    "revoke_role",
    "RoleNotFound",
    "PermissionScope",
    "PERMISSIONS",
    "PERMISSION_SCOPE",
]
