# TODO: need to rename this file to a better more accurate name

from app.core.permissions.scope import Scope
from app.lib.permissions.hooks import PERMISSIONS, SCOPES


def create_permisson(permission: str) -> None:
    PERMISSIONS.add_item(
        # pluging,
        permission
    )
    return permission


def create_scope(name: str, parent: Scope | None):
    scope = Scope(name, parent)
    SCOPES.add_item(
        # plugin,
        scope
    )
    return scope
