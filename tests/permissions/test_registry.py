import pytest

from app.core.permissions import PERMISSIONS, Permission
from app.core.permissions.exceptions import PermissionNotFound, PermissionScopeNotFound
from app.core.permissions.scopes import PERMISSION_SCOPES, PermissionScope
from app.lib.hooks import SingleNamedItemHook
from app.lib.permissions.registry import PermissionScopesRegistry, PermissionsRegistry


@pytest.fixture
def permissions_hook(monkeypatch: pytest.MonkeyPatch) -> SingleNamedItemHook[Permission]:
    """Patch PermissionsRegistry onto a fresh, isolated hook and return it to populate."""
    hook: SingleNamedItemHook[Permission] = SingleNamedItemHook()
    monkeypatch.setattr(PermissionsRegistry, "_hook", hook)
    return hook


@pytest.fixture
def scopes_hook(monkeypatch: pytest.MonkeyPatch) -> SingleNamedItemHook[PermissionScope]:
    """Patch PermissionScopesRegistry onto a fresh, isolated hook and return it to populate."""
    hook: SingleNamedItemHook[PermissionScope] = SingleNamedItemHook()
    monkeypatch.setattr(PermissionScopesRegistry, "_hook", hook)
    return hook


def test_get_permission_returns_the_registered_object(permissions_hook: SingleNamedItemHook[Permission]) -> None:
    permission = Permission("assignment.grade")
    permissions_hook.add_item(permission)

    assert PermissionsRegistry().get("assignment.grade") is permission


def test_get_unknown_permission_raises(permissions_hook: SingleNamedItemHook[Permission]) -> None:
    with pytest.raises(PermissionNotFound):
        PermissionsRegistry().get("nope")


def test_all_returns_every_registered_permission(permissions_hook: SingleNamedItemHook[Permission]) -> None:
    first = Permission("a")
    second = Permission("b")
    permissions_hook.add_item(first)
    permissions_hook.add_item(second)

    assert PermissionsRegistry().all() == [first, second]


def test_all_is_empty_for_an_empty_hook(permissions_hook: SingleNamedItemHook[Permission]) -> None:
    assert PermissionsRegistry().all() == []


def test_get_permission_scope_returns_the_registered_object(scopes_hook: SingleNamedItemHook[PermissionScope]) -> None:
    scope = PermissionScope("course")
    scopes_hook.add_item(scope)

    assert PermissionScopesRegistry().get("course") is scope


def test_get_unknown_permission_scope_raises(scopes_hook: SingleNamedItemHook[PermissionScope]) -> None:
    with pytest.raises(PermissionScopeNotFound):
        PermissionScopesRegistry().get("course")


def test_registries_read_the_global_hooks_by_default() -> None:
    # Unpatched, each registry's class-attribute hook is the real global hook, which carries the
    # core vocabulary registered at import: the email-whitelist permissions and the global scope.
    assert PermissionsRegistry().get("email.whitelist.read") is PERMISSIONS.get("email.whitelist.read")
    assert PermissionScopesRegistry().get("global") is PERMISSION_SCOPES.get("global")
