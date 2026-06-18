"""Public API for the permissions (scoped RBAC) framework.

Application code and plugins import the permissions surface from here, never from
``app.permissions.*`` directly.
"""

from app.permissions.constants import SCOPE_GLOBAL
from app.permissions.enums import EmailWhitelistPermissions
from app.permissions.exceptions import RoleNotFound
from app.permissions.service import PermissionService

__all__ = ["EmailWhitelistPermissions", "PermissionService", "RoleNotFound", "SCOPE_GLOBAL"]
