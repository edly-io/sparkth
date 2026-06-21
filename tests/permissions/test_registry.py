import pytest

from app.core.permissions.exceptions import PermissionNotFound, ScopeNotFound
from app.core.permissions.scope import PermissionScope
from app.lib.permissions import registry
from app.lib.permissions.registry import (
    PermissionScopesRegistry,
    PermissionsRegistry,
    initialize_permission_scopes_registry,
    initialize_permissions_registry,
)


@pytest.fixture
def permissions() -> PermissionsRegistry:
    return PermissionsRegistry()


@pytest.fixture
def scopes() -> PermissionScopesRegistry:
    return PermissionScopesRegistry()


@pytest.fixture(autouse=True)
def _reset_registries() -> None:
    PermissionsRegistry().clear()
    PermissionScopesRegistry().clear()


def test_registries_are_singletons() -> None:
    assert PermissionsRegistry() is PermissionsRegistry()
    assert PermissionScopesRegistry() is PermissionScopesRegistry()


def test_add_permission_returns_it(permissions: PermissionsRegistry) -> None:
    assert permissions.add("assignment.grade") == "assignment.grade"


def test_get_permission_returns_added(permissions: PermissionsRegistry) -> None:
    permissions.add("assignment.grade")
    assert permissions.get("assignment.grade") == "assignment.grade"


def test_add_permission_is_idempotent(permissions: PermissionsRegistry) -> None:
    permissions.add("assignment.grade")
    permissions.add("assignment.grade")
    assert permissions.all() == ["assignment.grade"]


def test_get_unknown_permission_raises(permissions: PermissionsRegistry) -> None:
    with pytest.raises(PermissionNotFound):
        permissions.get("nope")


def test_clear_empties_permissions(permissions: PermissionsRegistry) -> None:
    permissions.add("assignment.grade")
    permissions.clear()
    assert permissions.all() == []


def test_add_scope_returns_it(scopes: PermissionScopesRegistry) -> None:
    scope = PermissionScope("global")
    assert scopes.add(scope) is scope


def test_get_scope_returns_added(scopes: PermissionScopesRegistry) -> None:
    scope = PermissionScope("global")
    scopes.add(scope)
    assert scopes.get("global") is scope


def test_get_unknown_scope_raises(scopes: PermissionScopesRegistry) -> None:
    with pytest.raises(ScopeNotFound):
        scopes.get("course")


def test_add_child_after_parent_links(scopes: PermissionScopesRegistry) -> None:
    root = PermissionScope("global")
    course = PermissionScope("course", parent=root)
    scopes.add(root)
    scopes.add(course)

    assert scopes.get("course").parent is root


def test_add_scope_with_unregistered_parent_raises(scopes: PermissionScopesRegistry) -> None:
    # A scope's parent must be registered first; we do not auto-create ancestors.
    course = PermissionScope("course", parent=PermissionScope("global"))
    with pytest.raises(ScopeNotFound):
        scopes.add(course)


def test_add_chain_in_hierarchy_order(scopes: PermissionScopesRegistry) -> None:
    root = PermissionScope("global")
    course = PermissionScope("course", parent=root)
    quiz = PermissionScope("quiz", parent=course)
    scopes.add(root)
    scopes.add(course)
    scopes.add(quiz)

    assert scopes.get("global") is root
    assert scopes.get("course") is course
    assert scopes.get("quiz") is quiz


def test_clear_empties_scopes(scopes: PermissionScopesRegistry) -> None:
    scopes.add(PermissionScope("global"))
    scopes.clear()
    with pytest.raises(ScopeNotFound):
        scopes.get("global")


def test_initialize_permissions_registry_loads_hook_items(monkeypatch: pytest.MonkeyPatch) -> None:
    # The hook yields (plugin, item) pairs; the loader must unpack and register the item.
    monkeypatch.setattr(registry.PERMISSIONS, "iter_items", lambda: iter([(object(), "assignment.grade")]))
    initialize_permissions_registry()
    assert PermissionsRegistry().get("assignment.grade") == "assignment.grade"


def test_initialize_scopes_registry_loads_hook_items(monkeypatch: pytest.MonkeyPatch) -> None:
    root = PermissionScope("global")
    course = PermissionScope("course", parent=root)
    # Parent must be registered before its child, so the hook must yield it first.
    monkeypatch.setattr(registry.PERMISSION_SCOPE, "iter_items", lambda: iter([(object(), root), (object(), course)]))
    initialize_permission_scopes_registry()
    assert PermissionScopesRegistry().get("course") is course
