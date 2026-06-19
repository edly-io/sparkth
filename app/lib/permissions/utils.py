# TODO: need to rename this file to a better more accurate name

from app.core.permissions.scope import Scope
from app.lib.permissions.hooks import PERMISSIONS, SCOPES


def create_permisson(permission: str) -> None:
    PERMISSIONS.add_item(permission)
    return permission


def create_scope(name: str, parent: Scope | None):
    scope = Scope(name, parent)
    SCOPES.add_item(scope)
    return scope


# Need to integrate something like this in the app's lifecycle
# TODO: incomplete placeholder — temporarily commented out so the suite parses.
# def add_permissions_to_db():  # placeholder name
#     for permission in PERMISSIONS.iter_items()
