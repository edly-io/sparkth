"""Public API for the permissions framework.

Application code and plugins import the permissions surface from here, never from
``sparkth.core.permissions`` or the hook modules directly. A plugin declares its
permissions and scope kinds at module level in its ``plugin.py``, or in a module of the plugin
that its routes import when they need the constant, with ``Permission.create()``
and ``PermissionScope.create()`` (or ``ObjectlessPermissionScope.create()`` for a singleton
scope), never in the plugin class's ``__init__``, which runs more than once::

    from sparkth.lib.permissions import Permission
    from sparkth.lib.permissions.scopes import GLOBAL, PermissionScope

    COURSE = PermissionScope.create("course", parent=GLOBAL)
    COURSE_GRADE = Permission.create("course.grade")
"""

from sparkth.core.permissions import (
    ANALYTICS_READ,
    AUDIT_READ,
    EMAIL_WHITELIST_CREATE,
    EMAIL_WHITELIST_DELETE,
    EMAIL_WHITELIST_READ,
    GROUP_CREATE,
    GROUP_DELETE,
    GROUP_READ,
    GROUP_UPDATE,
    LLM_CONFIG_CREATE,
    LLM_CONFIG_DELETE,
    LLM_CONFIG_READ,
    LLM_CONFIG_UPDATE,
    PERMISSION_READ,
    ROLE_CREATE,
    ROLE_DELETE,
    ROLE_READ,
    ROLE_UPDATE,
    USER_READ,
    Permission,
    get_permission,
)
from sparkth.core.permissions.dependencies import get_listed_owner_id, object_id_str_to_int
from sparkth.core.permissions.engine import can, has_role
from sparkth.core.permissions.grants import DEFAULT_USER_ROLE, assign_default_role, assign_role, revoke_role
from sparkth.core.permissions.groups import (
    add_group_member,
    assign_role_to_group,
    get_group_by_name,
    remove_group_member,
    revoke_role_from_group,
)
from sparkth.core.permissions.scopes import get_permission_scope

__all__ = [
    "DEFAULT_USER_ROLE",
    "assign_default_role",
    "add_group_member",
    "assign_role",
    "assign_role_to_group",
    "can",
    "get_listed_owner_id",
    "object_id_str_to_int",
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
    "PERMISSION_READ",
    "ANALYTICS_READ",
    "AUDIT_READ",
    "USER_READ",
    "LLM_CONFIG_CREATE",
    "LLM_CONFIG_READ",
    "LLM_CONFIG_UPDATE",
    "LLM_CONFIG_DELETE",
]
