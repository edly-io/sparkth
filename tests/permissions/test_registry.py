import pytest

from app.core.permissions import PERMISSIONS, Permission
from app.core.permissions.exceptions import PermissionNotFound, PermissionScopeNotFound
from app.core.permissions.scopes import PERMISSION_SCOPES, PermissionScope
from app.lib.hooks import SingleNamedItemHook
from app.lib.permissions.registry import PermissionScopesRegistry, PermissionsRegistry


def test_get_permission_returns_the_registered_object() -> None:
    hook: SingleNamedItemHook[Permission] = SingleNamedItemHook()
    permission = Permission("assignment.grade")
    hook.add_item(permission)

    assert PermissionsRegistry(hook).get("assignment.grade") is permission


def test_get_unknown_permission_raises() -> None:
    registry = PermissionsRegistry(SingleNamedItemHook())

    with pytest.raises(PermissionNotFound):
        registry.get("nope")


def test_all_returns_every_registered_permission() -> None:
    hook: SingleNamedItemHook[Permission] = SingleNamedItemHook()
    first = Permission("a")
    second = Permission("b")
    hook.add_item(first)
    hook.add_item(second)

    assert PermissionsRegistry(hook).all() == [first, second]


def test_all_is_empty_for_an_empty_hook() -> None:
    assert PermissionsRegistry(SingleNamedItemHook()).all() == []


def test_get_permission_scope_returns_the_registered_object() -> None:
    hook: SingleNamedItemHook[PermissionScope] = SingleNamedItemHook()
    scope = PermissionScope("course")
    hook.add_item(scope)

    assert PermissionScopesRegistry(hook).get("course") is scope


def test_get_unknown_permission_scope_raises() -> None:
    registry = PermissionScopesRegistry(SingleNamedItemHook())

    with pytest.raises(PermissionScopeNotFound):
        registry.get("course")


def test_registries_default_to_the_global_hooks() -> None:
    # No-arg construction reads the global hooks, which carry the core vocabulary registered at
    # import: the email-whitelist permissions and the global scope.
    assert PermissionsRegistry().get("email.whitelist.read") is PERMISSIONS.get("email.whitelist.read")
    assert PermissionScopesRegistry().get("global") is PERMISSION_SCOPES.get("global")
