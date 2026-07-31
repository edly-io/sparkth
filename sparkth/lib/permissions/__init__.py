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
    GROUP_CREATE,
    GROUP_DELETE,
    GROUP_READ,
    GROUP_UPDATE,
    ORGANIZATION_UNIT_CREATE,
    ORGANIZATION_UNIT_DELETE,
    ORGANIZATION_UNIT_READ,
    ORGANIZATION_UNIT_UPDATE,
    PERMISSION_READ,
    ROLE_CREATE,
    ROLE_DELETE,
    ROLE_READ,
    ROLE_UPDATE,
    Permission,
    assign_role,
    can,
    get_permission,
    has_role,
    revoke_role,
)
from sparkth.core.permissions.groups import (
    add_group_member,
    assign_role_to_group,
    get_group_by_name,
    remove_group_member,
    revoke_role_from_group,
)
from sparkth.core.permissions.scopes import get_permission_scope

__all__ = [
    "add_group_member",
    "assign_role",
    "assign_role_to_group",
    "can",
    "get_group_by_name",
    "get_permission",
    "get_permission_scope",
    "has_role",
    "remove_group_member",
    "revoke_role",
    "revoke_role_from_group",
    "Permission",
    "EMAIL_WHITELIST_READ",
    "EMAIL_WHITELIST_CREATE",
    "EMAIL_WHITELIST_DELETE",
    "ROLE_CREATE",
    "ROLE_READ",
    "ROLE_UPDATE",
    "ROLE_DELETE",
    "GROUP_CREATE",
    "GROUP_READ",
    "GROUP_UPDATE",
    "GROUP_DELETE",
    "ORGANIZATION_UNIT_CREATE",
    "ORGANIZATION_UNIT_READ",
    "ORGANIZATION_UNIT_UPDATE",
    "ORGANIZATION_UNIT_DELETE",
    "PERMISSION_READ",
    "ANALYTICS_READ",
]
