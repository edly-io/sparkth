import pytest

from app.core.permissions.exceptions import InvalidScopeObjectId, PermissionScopeNotFound
from app.core.permissions.scopes import (
    GLOBAL,
    ObjectlessPermissionScope,
    PermissionScope,
    get_permission_scope,
)
from app.lib.permissions.scopes import ROLE, WHITELIST


def test_create_with_unregistered_parent_raises() -> None:
    # A scope's parent must already be registered on the PERMISSION_SCOPES hook; ancestors are
    # never auto-created. The orphan parent is built with the bare (test-only) constructor, so it
    # was never registered, and create() must reject the child before registering it.
    orphan = PermissionScope("orphan-parent", parent=GLOBAL)

    with pytest.raises(PermissionScopeNotFound):
        PermissionScope.create("orphan-child", parent=orphan)


def test_global_is_objectless_scope() -> None:
    assert isinstance(GLOBAL, ObjectlessPermissionScope)


def test_whitelist_scope_registered_under_global() -> None:
    assert get_permission_scope("whitelist") is WHITELIST
    assert isinstance(WHITELIST, ObjectlessPermissionScope)
    assert WHITELIST.parent is GLOBAL
    assert WHITELIST.get_parents() == [GLOBAL]


def test_role_scope_registered_under_global() -> None:
    # The role scope names one specific role (via scope_object_id), so it is an object-bearing
    # PermissionScope (not an ObjectlessPermissionScope like global/whitelist); it hangs directly
    # off the global root.
    assert get_permission_scope("role") is ROLE
    assert isinstance(ROLE, PermissionScope)
    assert not isinstance(ROLE, ObjectlessPermissionScope)
    assert ROLE.parent is GLOBAL
    assert ROLE.get_parents() == [GLOBAL]
    # A global grant cascades to a role-scoped check; the role itself carries the checked id.
    assert ROLE.scope_chain("5") == [("role", "5"), ("global", None)]


class TestPermissionScope:
    # PermissionScope is the concrete, object-bearing scope — the common case.
    def test_validate_object_id_accepts_object_id(self) -> None:
        PermissionScope("s").validate_object_id("42")  # no raise

    def test_validate_object_id_rejects_none(self) -> None:
        with pytest.raises(InvalidScopeObjectId):
            PermissionScope("s").validate_object_id(None)

    def test_validate_scope_param_accepts_param(self) -> None:
        PermissionScope("s").validate_scope_param("thing_id")  # no raise

    def test_validate_scope_param_rejects_none(self) -> None:
        with pytest.raises(ValueError):
            PermissionScope("s").validate_scope_param(None)


class TestObjectlessPermissionScope:
    def test_validate_object_id_accepts_none(self) -> None:
        ObjectlessPermissionScope("s").validate_object_id(None)  # no raise

    def test_validate_object_id_rejects_object_id(self) -> None:
        with pytest.raises(InvalidScopeObjectId):
            ObjectlessPermissionScope("s").validate_object_id("42")

    def test_validate_scope_param_accepts_none(self) -> None:
        ObjectlessPermissionScope("s").validate_scope_param(None)  # no raise

    def test_validate_scope_param_rejects_param(self) -> None:
        with pytest.raises(ValueError):
            ObjectlessPermissionScope("s").validate_scope_param("thing_id")


class TestScopeChain:
    def test_objectless_target_includes_objectless_ancestors(self) -> None:
        # WHITELIST (objectless) under GLOBAL (objectless): both appear, each with a NULL id.
        assert WHITELIST.scope_chain(None) == [("whitelist", None), ("global", None)]

    def test_object_target_under_objectless_ancestor(self) -> None:
        course = PermissionScope("course", parent=GLOBAL)
        # The course itself carries the checked id; its objectless ancestor cascades with NULL.
        assert course.scope_chain("5") == [("course", "5"), ("global", None)]

    def test_object_bearing_ancestor_does_not_cascade_yet(self) -> None:
        # activity -> course -> global. The object-bearing `course` ancestor contributes nothing
        # (resolving its id needs a materialized path; deferred, #420 Phase 2); only the objectless
        # GLOBAL root cascades. So a course-level grant does NOT reach an activity yet.
        course = PermissionScope("course", parent=GLOBAL)
        activity = PermissionScope("activity", parent=course)
        assert activity.scope_chain("Y") == [("activity", "Y"), ("global", None)]
