"""Public API for the permissions (scoped RBAC) framework.

Application code and plugins import the permissions surface from here, never from
``app.permissions.*`` directly.
"""

from app.permissions.constants import SCOPE_GLOBAL as SCOPE_GLOBAL
from app.permissions.exceptions import RoleNotFound as RoleNotFound
from app.permissions.service import PermissionService as PermissionService
