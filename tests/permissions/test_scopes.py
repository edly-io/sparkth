import pytest

from app.core.permissions.exceptions import PermissionScopeNotFound
from app.core.permissions.scopes import GLOBAL, PermissionScope, get_permission_scope
from app.lib.permissions.scopes import WHITELIST


def test_create_with_unregistered_parent_raises() -> None:
    # A scope's parent must already be registered on the PERMISSION_SCOPES hook; ancestors are
    # never auto-created. The orphan parent is built with the bare (test-only) constructor, so it
    # was never registered, and create() must reject the child before registering it.
    orphan = PermissionScope("orphan-parent")

    with pytest.raises(PermissionScopeNotFound):
        PermissionScope.create("orphan-child", parent=orphan)


def test_scope_objectless_defaults_false() -> None:
    assert PermissionScope("course").objectless is False


def test_global_scope_is_objectless() -> None:
    assert GLOBAL.objectless is True


def test_whitelist_scope_registered_under_global() -> None:
    assert get_permission_scope("whitelist") is WHITELIST
    assert WHITELIST.parent is GLOBAL
    assert WHITELIST.objectless is True
    assert WHITELIST.get_parents() == [GLOBAL]
