import pytest

from app.core.permissions.exceptions import PermissionScopeNotFound
from app.core.permissions.scopes import PermissionScope


def test_create_with_unregistered_parent_raises() -> None:
    # A scope's parent must already be registered on the PERMISSION_SCOPES hook; ancestors are
    # never auto-created. The orphan parent is built with the bare (test-only) constructor, so it
    # was never registered, and create() must reject the child before registering it.
    orphan = PermissionScope("orphan-parent")

    with pytest.raises(PermissionScopeNotFound):
        PermissionScope.create("orphan-child", parent=orphan)
