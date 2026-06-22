# TODO: need to rename this file to a better more accurate name

from app.core.permissions.scope import PermissionScope
from app.lib.permissions.hooks import PERMISSIONS, PERMISSION_SCOPE


def create_permisson(permission: str) -> None:
    # Check if the permisson already exists
    PERMISSIONS.add_item(
        # pluging,
        permission
    )
    return permission


def create_permission_scope(name: str, parent: PermissionScope | None):
    permission_scope = PermissionScope(name, parent)
    # Check if the permission scope already exists
    PERMISSION_SCOPE.add_item(
        # plugin,
        permission_scope
    )
    return permission_scope
