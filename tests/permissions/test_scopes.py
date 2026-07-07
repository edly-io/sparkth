import pytest

from app.core.permissions.exceptions import InvalidScopeObjectId, PermissionScopeNotFound
from app.core.permissions.scopes import (
    GLOBAL,
    ObjectlessScope,
    ObjectScope,
    PermissionScope,
    get_permission_scope,
)
from app.lib.permissions.scopes import WHITELIST


def test_create_with_unregistered_parent_raises() -> None:
    # A scope's parent must already be registered on the PERMISSION_SCOPES hook; ancestors are
    # never auto-created. The orphan parent is built with the bare (test-only) constructor, so it
    # was never registered, and create() must reject the child before registering it.
    orphan = ObjectScope("orphan-parent", parent=GLOBAL)

    with pytest.raises(PermissionScopeNotFound):
        ObjectScope.create("orphan-child", parent=orphan)


def test_permission_scope_base_is_abstract() -> None:
    # PermissionScope is the abstract base; callers must pick a concrete kind.
    with pytest.raises(TypeError):
        PermissionScope("nope")  # type: ignore[abstract]


def test_global_is_objectless_scope() -> None:
    assert isinstance(GLOBAL, ObjectlessScope)


def test_whitelist_scope_registered_under_global() -> None:
    assert get_permission_scope("whitelist") is WHITELIST
    assert isinstance(WHITELIST, ObjectlessScope)
    assert WHITELIST.parent is GLOBAL
    assert WHITELIST.get_parents() == [GLOBAL]


class TestObjectlessScope:
    def test_validate_object_id_accepts_none(self) -> None:
        ObjectlessScope("s").validate_object_id(None)  # no raise

    def test_validate_object_id_rejects_object_id(self) -> None:
        with pytest.raises(InvalidScopeObjectId):
            ObjectlessScope("s").validate_object_id("42")

    def test_validate_scope_param_accepts_none(self) -> None:
        ObjectlessScope("s").validate_scope_param(None)  # no raise

    def test_validate_scope_param_rejects_param(self) -> None:
        with pytest.raises(ValueError):
            ObjectlessScope("s").validate_scope_param("thing_id")


class TestObjectScope:
    def test_validate_object_id_accepts_object_id(self) -> None:
        ObjectScope("s").validate_object_id("42")  # no raise

    def test_validate_object_id_rejects_none(self) -> None:
        with pytest.raises(InvalidScopeObjectId):
            ObjectScope("s").validate_object_id(None)

    def test_validate_scope_param_accepts_param(self) -> None:
        ObjectScope("s").validate_scope_param("thing_id")  # no raise

    def test_validate_scope_param_rejects_none(self) -> None:
        with pytest.raises(ValueError):
            ObjectScope("s").validate_scope_param(None)


class TestScopeChain:
    def test_objectless_target_includes_objectless_ancestors(self) -> None:
        # WHITELIST (objectless) under GLOBAL (objectless): both appear, each with a NULL id.
        assert WHITELIST.scope_chain(None) == [("whitelist", None), ("global", None)]

    def test_object_target_under_objectless_ancestor(self) -> None:
        course = ObjectScope("course", parent=GLOBAL)
        # The course itself carries the checked id; its objectless ancestor cascades with NULL.
        assert course.scope_chain("5") == [("course", "5"), ("global", None)]

    def test_object_bearing_ancestor_does_not_cascade_yet(self) -> None:
        # activity -> course -> global. The object-bearing `course` ancestor contributes nothing
        # (resolving its id needs a materialized path; deferred, #420 Phase 2); only the objectless
        # GLOBAL root cascades. So a course-level grant does NOT reach an activity yet.
        course = ObjectScope("course", parent=GLOBAL)
        activity = ObjectScope("activity", parent=course)
        assert activity.scope_chain("Y") == [("activity", "Y"), ("global", None)]
