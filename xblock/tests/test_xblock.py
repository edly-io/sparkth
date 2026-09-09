"""Tests for the XBlock's two views and the markup they build.

The block constructs against XBlock's own ``ToyRuntime`` given real ``ScopeIds``, so both
views can be rendered here rather than only their helper functions. That matters: a test that
builds its own markup cannot catch a view wired to the wrong permission.
"""

import json
from base64 import urlsafe_b64decode
from typing import Any

import pytest
from sparkth_pxc.xblock import _EDITOR_NOTICE, SparkthPxcXBlock, build_editor_html, build_embed_iframe
from xblock.fields import ScopeIds
from xblock.test.toy_runtime import ToyRuntime


def claims_in(html: str) -> dict[str, Any]:
    """The claims carried by the launch token in this markup's iframe src."""
    token = html.split("token=")[1].split('"')[0]
    payload = token.split(".")[0]
    decoded: dict[str, Any] = json.loads(urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    return decoded


@pytest.fixture
def block() -> SparkthPxcXBlock:
    """A constructed block with an activity and placement already set."""
    made = SparkthPxcXBlock(ToyRuntime(), scope_ids=ScopeIds("learner-7", "pxc", "def-1", "usage-1"))
    made.activity = "mcq"
    made.placement = "placement-1"
    return made


def test_the_iframe_points_at_sparkths_embed_route_with_a_token() -> None:
    html = build_embed_iframe(
        "https://sparkth.example/", "mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", "play", "s", 300
    )

    assert 'src="https://sparkth.example/api/v1/pxc/embed?token=' in html
    assert html.startswith("<iframe")


def test_the_iframe_is_sandboxed() -> None:
    html = build_embed_iframe(
        "https://sparkth.example", "mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", "play", "s", 300
    )

    assert 'sandbox="allow-scripts allow-forms allow-same-origin"' in html


def test_a_trailing_slash_on_the_base_url_does_not_double_up() -> None:
    html = build_embed_iframe(
        "https://sparkth.example/", "mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", "play", "s", 300
    )

    assert "example//api" not in html


def test_the_token_carries_the_requested_permission() -> None:
    edit = build_embed_iframe(
        "https://sparkth.example", "mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", "edit", "s", 300
    )

    assert claims_in(edit)["prm"] == "edit"


def test_the_editor_markup_explains_that_studios_buttons_do_not_apply() -> None:
    # An editor learns this from the screen or not at all; the README reaches nobody mid-edit.
    html = build_editor_html("https://sparkth.example", "mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", "s", 300)

    assert "stored in Sparkth" in html
    assert "Cancel" in html
    # A substring check alone would still pass with the iframe placed first, leaving the
    # notice below a min-height:24em frame where the author never sees it.
    assert html.startswith(_EDITOR_NOTICE)


def test_the_learner_view_asks_for_play(block: SparkthPxcXBlock) -> None:
    assert claims_in(str(block.student_view().content))["prm"] == "play"


def test_a_rendered_views_token_carries_the_viewers_id(block: SparkthPxcXBlock) -> None:
    # The fixture's ScopeIds names this viewer "learner-7"; nothing else here checks that id,
    # as opposed to any other constant, actually reaches the token.
    assert claims_in(str(block.student_view().content))["uid"] == "learner-7"


def test_the_editing_view_asks_for_edit(block: SparkthPxcXBlock) -> None:
    # The wiring test: build_editor_html could be perfect while studio_view called the wrong
    # helper, and no test of either function alone would notice.
    assert claims_in(str(block.studio_view().content))["prm"] == "edit"


def test_only_the_editing_view_carries_the_notice(block: SparkthPxcXBlock) -> None:
    assert "stored in Sparkth" in str(block.studio_view().content)
    assert "stored in Sparkth" not in str(block.student_view().content)
