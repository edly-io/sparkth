import logging

import pytest

from app.core.permissions import Permission, hooks
from app.core.permissions.exceptions import PermissionNotFound, PermissionScopeNotFound
from app.core.permissions.scopes import PermissionScope
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
def permission_scopes() -> PermissionScopesRegistry:
    return PermissionScopesRegistry()


@pytest.fixture(autouse=True)
def _reset_registries() -> None:
    PermissionsRegistry().clear()
    PermissionScopesRegistry().clear()


def test_registries_are_singletons() -> None:
    assert PermissionsRegistry() is PermissionsRegistry()
    assert PermissionScopesRegistry() is PermissionScopesRegistry()


def test_construction_does_not_seed_permission_scopes() -> None:
    # Scopes are no longer seeded at construction; the registry is populated solely by
    # initialize_permission_scopes_registry() reading from the PERMISSION_SCOPES hook.
    PermissionScopesRegistry.instance = None
    fresh = PermissionScopesRegistry()
    with pytest.raises(PermissionScopeNotFound):
        fresh.get("global")


def test_construction_does_not_seed_permissions() -> None:
    # Permissions are no longer seeded at construction; the registry is populated solely
    # by initialize_permissions_registry() reading from the PERMISSIONS hook.
    PermissionsRegistry.instance = None
    fresh = PermissionsRegistry()
    assert fresh.all() == []


def test_add_permission_returns_it(permissions: PermissionsRegistry) -> None:
    assert permissions.add("assignment.grade") == "assignment.grade"


def test_get_permission_returns_added(permissions: PermissionsRegistry) -> None:
    permissions.add("assignment.grade")
    assert permissions.get("assignment.grade") == "assignment.grade"


def test_add_duplicate_permission_logs_and_ignores(
    permissions: PermissionsRegistry, caplog: pytest.LogCaptureFixture
) -> None:
    permissions.add("assignment.grade")
    with caplog.at_level(logging.WARNING):
        permissions.add("assignment.grade")
    assert permissions.all() == ["assignment.grade"]
    assert "assignment.grade" in caplog.text


def test_get_unknown_permission_raises(permissions: PermissionsRegistry) -> None:
    with pytest.raises(PermissionNotFound):
        permissions.get("nope")


def test_clear_empties_permissions(permissions: PermissionsRegistry) -> None:
    permissions.add("assignment.grade")
    permissions.clear()
    assert permissions.all() == []


def test_add_permission_scope_returns_it(permission_scopes: PermissionScopesRegistry) -> None:
    permission_scope = PermissionScope("global")
    assert permission_scopes.add(permission_scope) is permission_scope


def test_get_permission_scope_returns_added(permission_scopes: PermissionScopesRegistry) -> None:
    permission_scope = PermissionScope("global")
    permission_scopes.add(permission_scope)
    assert permission_scopes.get("global") is permission_scope


def test_get_unknown_permission_scope_raises(permission_scopes: PermissionScopesRegistry) -> None:
    with pytest.raises(PermissionScopeNotFound):
        permission_scopes.get("course")


def test_add_duplicate_permission_scope_logs_and_ignores(
    permission_scopes: PermissionScopesRegistry, caplog: pytest.LogCaptureFixture
) -> None:
    first = permission_scopes.add(PermissionScope("global"))
    with caplog.at_level(logging.WARNING):
        second = permission_scopes.add(PermissionScope("global"))
    assert second is first
    assert "global" in caplog.text


def test_add_child_after_parent_links(permission_scopes: PermissionScopesRegistry) -> None:
    root = PermissionScope("global")
    course = PermissionScope("course", parent=root)
    permission_scopes.add(root)
    permission_scopes.add(course)

    assert permission_scopes.get("course").parent is root


def test_add_permission_scope_with_unregistered_parent_raises(permission_scopes: PermissionScopesRegistry) -> None:
    # A permission scope's parent must be registered first; we do not auto-create ancestors.
    course = PermissionScope("course", parent=PermissionScope("global"))
    with pytest.raises(PermissionScopeNotFound):
        permission_scopes.add(course)


def test_add_chain_in_hierarchy_order(permission_scopes: PermissionScopesRegistry) -> None:
    root = PermissionScope("global")
    course = PermissionScope("course", parent=root)
    quiz = PermissionScope("quiz", parent=course)
    permission_scopes.add(root)
    permission_scopes.add(course)
    permission_scopes.add(quiz)

    assert permission_scopes.get("global") is root
    assert permission_scopes.get("course") is course
    assert permission_scopes.get("quiz") is quiz


def test_clear_empties_permission_scopes(permission_scopes: PermissionScopesRegistry) -> None:
    permission_scopes.add(PermissionScope("global"))
    permission_scopes.clear()
    with pytest.raises(PermissionScopeNotFound):
        permission_scopes.get("global")


def test_initialize_permissions_registry_loads_hook_items(monkeypatch: pytest.MonkeyPatch) -> None:
    # The hook yields Permission objects; the loader unwraps each to its name string.
    monkeypatch.setattr(hooks.PERMISSIONS, "iter_items", lambda: iter([Permission("assignment.grade")]))
    initialize_permissions_registry()
    assert PermissionsRegistry().get("assignment.grade") == "assignment.grade"


def test_initialize_permission_scopes_registry_loads_hook_items(monkeypatch: pytest.MonkeyPatch) -> None:
    root = PermissionScope("global")
    course = PermissionScope("course", parent=root)
    # The hook yields scopes in insertion order, so a parent precedes its child.
    monkeypatch.setattr(hooks.PERMISSION_SCOPES, "iter_items", lambda: iter([root, course]))
    initialize_permission_scopes_registry()
    assert PermissionScopesRegistry().get("course") is course
