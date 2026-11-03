import pytest
from sqlmodel import Field
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.permissions.exceptions import InvalidScopeObjectId, PermissionScopeNotFound
from sparkth.core.permissions.scopes import (
    GLOBAL,
    ObjectlessPermissionScope,
    PermissionScope,
    get_permission_scope,
)
from sparkth.core.permissions.scopes.mixins import ScopeObjectMixin
from sparkth.core.permissions.utils import build_scope_path
from sparkth.lib.permissions.scopes import GROUP, ROLE, WHITELIST


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
    assert ROLE.scope_chain("role:5") == [("role", "5"), ("global", None)]


def test_group_scope_registered_under_global() -> None:
    # A grant at group:<id> covers one group; a global grant cascades down to it.
    assert get_permission_scope("group") is GROUP
    assert GROUP.scope_chain("group:5") == [("group", "5"), ("global", None)]


class TestPermissionScope:
    # PermissionScope is the concrete, object-bearing scope — the common case.
    def test_validate_object_id_accepts_object_id(self) -> None:
        PermissionScope("s").validate_object_id("42")  # no raise

    def test_validate_object_id_rejects_none(self) -> None:
        with pytest.raises(InvalidScopeObjectId):
            PermissionScope("s").validate_object_id(None)

    def test_validate_scope_object_id_arguments_accepts_scope_param(self) -> None:
        PermissionScope("s").validate_scope_object_id_arguments("thing_id", None)  # no raise

    def test_validate_scope_object_id_arguments_accepts_object_id(self) -> None:
        PermissionScope("s").validate_scope_object_id_arguments(None, "5")  # no raise

    def test_validate_scope_object_id_arguments_rejects_neither(self) -> None:
        with pytest.raises(ValueError):
            PermissionScope("s").validate_scope_object_id_arguments(None, None)

    def test_validate_scope_object_id_arguments_rejects_both(self) -> None:
        with pytest.raises(ValueError):
            PermissionScope("s").validate_scope_object_id_arguments("thing_id", "5")


class TestObjectlessPermissionScope:
    def test_validate_object_id_accepts_none(self) -> None:
        ObjectlessPermissionScope("s").validate_object_id(None)  # no raise

    def test_validate_object_id_rejects_object_id(self) -> None:
        with pytest.raises(InvalidScopeObjectId):
            ObjectlessPermissionScope("s").validate_object_id("42")

    def test_validate_scope_object_id_arguments_accepts_none(self) -> None:
        ObjectlessPermissionScope("s").validate_scope_object_id_arguments(None, None)  # no raise

    def test_validate_scope_object_id_arguments_rejects_param(self) -> None:
        with pytest.raises(ValueError):
            ObjectlessPermissionScope("s").validate_scope_object_id_arguments("thing_id", None)

    def test_validate_scope_object_id_arguments_rejects_object_id(self) -> None:
        with pytest.raises(ValueError):
            ObjectlessPermissionScope("s").validate_scope_object_id_arguments(None, "5")


class TestScopeChain:
    def test_objectless_target_includes_objectless_ancestors(self) -> None:
        # WHITELIST (objectless) under GLOBAL (objectless): both appear, each with a NULL id.
        assert WHITELIST.scope_chain(None) == [("whitelist", None), ("global", None)]

    def test_object_target_under_objectless_ancestor(self) -> None:
        course = PermissionScope("course", parent=GLOBAL)
        # The course itself carries the checked id; its objectless ancestor cascades with NULL.
        assert course.scope_chain("course:5") == [("course", "5"), ("global", None)]

    def test_object_bearing_ancestor_does_not_cascade_from_a_single_segment_path(self) -> None:
        # activity -> course -> global. The path names only the activity, and the object-bearing
        # `course` ancestor contributes nothing of its own; only the objectless GLOBAL root cascades.
        # So a course-level grant does NOT reach an activity named by a single-segment path.
        course = PermissionScope("course", parent=GLOBAL)
        activity = PermissionScope("activity", parent=course)
        assert activity.scope_chain("activity:Y") == [("activity", "Y"), ("global", None)]

    def test_no_path_gives_the_scope_itself_without_an_object_then_objectless_ancestors(self) -> None:
        course = PermissionScope("course", parent=GLOBAL)
        assert course.scope_chain(None) == [("course", None), ("global", None)]


def test_build_scope_path_for_root_level_object() -> None:
    org = PermissionScope("org", parent=GLOBAL)

    assert build_scope_path(org, "5") == "org:5"


def test_build_scope_path_appends_to_parent_path() -> None:
    org = PermissionScope("org", parent=GLOBAL)
    course = PermissionScope("course", parent=org)
    quiz = PermissionScope("quiz", parent=course)

    assert build_scope_path(quiz, "777", "org:5/course:123") == "org:5/course:123/quiz:777"


def test_scope_chain_from_path_returns_pairs_leaf_to_root_then_objectless_ancestors() -> None:
    org = PermissionScope("org", parent=GLOBAL)
    course = PermissionScope("course", parent=org)
    quiz = PermissionScope("quiz", parent=course)

    assert quiz.scope_chain("org:5/course:123/quiz:777") == [
        ("quiz", "777"),
        ("course", "123"),
        ("org", "5"),
        ("global", None),
    ]


def test_scope_chain_from_path_keeps_whitelist_style_objectless_ancestors() -> None:
    thing = PermissionScope("thing", parent=WHITELIST)

    assert thing.scope_chain("thing:1") == [("thing", "1"), ("whitelist", None), ("global", None)]


def test_scope_chain_rejects_a_path_ending_at_another_object() -> None:
    org = PermissionScope("org", parent=GLOBAL)
    course = PermissionScope("course", parent=org)
    quiz = PermissionScope("quiz", parent=course)

    with pytest.raises(ValueError):
        course.scope_chain("org:5/course:123/quiz:777")
    with pytest.raises(ValueError):
        GLOBAL.scope_chain("org:5")
    with pytest.raises(ValueError):
        quiz.scope_chain("org:5")


def test_build_scope_path_rejects_an_id_containing_a_slash() -> None:
    org = PermissionScope("org", parent=GLOBAL)

    with pytest.raises(ValueError):
        build_scope_path(org, "5/course:9")


class _Widget(ScopeObjectMixin, table=True):
    __tablename__ = "test_scope_object_widget"
    scope = PermissionScope("widget", parent=GLOBAL)

    id: int | None = Field(default=None, primary_key=True)


async def test_scope_object_round_trips_scope_path_and_scope_id(session: AsyncSession) -> None:
    widget = _Widget(id=7, scope_path=build_scope_path(_Widget.scope, "7"))
    session.add(widget)
    await session.flush()
    session.expunge(widget)

    loaded = await session.get(_Widget, 7)

    assert loaded is not None
    assert loaded.scope_path == "widget:7"
    assert loaded.scope_id == "7"
