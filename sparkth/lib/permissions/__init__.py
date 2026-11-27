"""Public API for the permissions framework.

Application code and plugins import the permissions surface from here, never from
``sparkth.core.permissions`` or the hook modules directly. A plugin declares its
permissions and scope kinds at module level in its ``plugin.py``, or in a module of the plugin
that its routes import when they need the constant, with ``Permission.create()``
and ``PermissionScope.create()`` (or ``ObjectlessPermissionScope.create()`` for a singleton
scope), never in the plugin class's ``__init__``, which runs more than once. Each permission
says what it is for::

    from sparkth.lib.i18n import gettext_noop
    from sparkth.lib.permissions import Permission
    from sparkth.lib.permissions.scopes import GLOBAL, PermissionScope

    COURSE = PermissionScope.create("course", parent=GLOBAL)
    COURSE_GRADE = Permission.create(
        "course.grade",
        gettext_noop("Grade courses"),
        gettext_noop("Mark submissions in a course."),
        gettext_noop("Courses"),
    )
"""

from sparkth.core.permissions import (
    ANALYTICS_READ,
    AUDIT_READ,
    EMAIL_WHITELIST_CREATE,
    EMAIL_WHITELIST_DELETE,
    EMAIL_WHITELIST_READ,
    FILE_UPLOAD,
    GROUP_CREATE,
    GROUP_DELETE,
    GROUP_MEMBER_ADD,
    GROUP_MEMBER_REMOVE,
    GROUP_READ,
    GROUP_UPDATE,
    LLM_CONFIG_CREATE,
    LLM_CONFIG_DELETE,
    LLM_CONFIG_READ,
    LLM_CONFIG_UPDATE,
    PERMISSION_READ,
    PLUGIN_MANAGE,
    PLUGIN_USE,
    ROLE_CREATE,
    ROLE_DELETE,
    ROLE_READ,
    ROLE_UPDATE,
    USER_READ,
    Permission,
    get_permission,
)
from sparkth.core.permissions.constants import PLUGIN_USER_ROLE, SPARKTH_USER_ROLE
from sparkth.core.permissions.dependencies import get_listed_owner_id, object_id_str_to_int
from sparkth.core.permissions.engine import (
    PermissionCheckQuery,
    batched_can,
    can,
    get_accessible_scope_object_ids,
    has_role,
)
from sparkth.core.permissions.enums import PermissionRisk
from sparkth.core.permissions.grants import assign_default_roles, assign_role, revoke_role
from sparkth.core.permissions.groups import (
    add_group_member,
    assign_role_to_group,
    get_group_by_name,
    remove_group_member,
    revoke_role_from_group,
)
from sparkth.core.permissions.scopes import get_permission_scope

__all__ = [
    "SPARKTH_USER_ROLE",
    "PLUGIN_USER_ROLE",
    "PermissionCheckQuery",
    "assign_default_roles",
    "add_group_member",
    "assign_role",
    "assign_role_to_group",
    "batched_can",
    "can",
    "get_accessible_scope_object_ids",
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
    "PermissionRisk",
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
    "GROUP_MEMBER_ADD",
    "GROUP_MEMBER_REMOVE",
    "PERMISSION_READ",
    "ANALYTICS_READ",
    "AUDIT_READ",
    "USER_READ",
    "LLM_CONFIG_CREATE",
    "LLM_CONFIG_READ",
    "LLM_CONFIG_UPDATE",
    "LLM_CONFIG_DELETE",
    "PLUGIN_USE",
    "PLUGIN_MANAGE",
    "FILE_UPLOAD",
]
