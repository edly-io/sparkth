from collections.abc import Iterator
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from sparkth.lib.content.exceptions import ContentBuildError
from sparkth.lib.content.hooks import (
    LMS_CONTENT_CONTRIBUTORS,
    ContentBlock,
    ContentContributor,
    register_content_contributor,
)
from sparkth.lib.enums import Method
from sparkth.lib.exceptions import LMSRequestError
from sparkth.plugins.openedx.schemas import AccessTokenPayload, AddPluginContentArgs
from sparkth.plugins.openedx.tools import openedx_add_plugin_content, openedx_list_content_contributors

AUTH = AccessTokenPayload(access_token="t", lms_url="https://lms", studio_url="https://studio")

# Every contributor name this module registers, so the cleanup fixture cannot desync from them.
CONTRIBUTOR_NAMES = ("fake", "broken", "bare", "canvas-only", "no-targets")


async def build_fake(course_id: str) -> ContentBlock:
    return ContentBlock("Fake Activity", "fake", {"placement": "p-1", "activity": "mcq"})


@pytest.fixture(autouse=True)
def unregister_contributors() -> Iterator[None]:
    # The hook is process-global, so a contributor registered by one test would otherwise be
    # listed by every later one.
    yield
    for name in CONTRIBUTOR_NAMES:
        LMS_CONTENT_CONTRIBUTORS.remove(name)


@pytest.fixture
def fake_contributor() -> ContentContributor:
    # Wraps (rather than replaces) build_fake so tests can assert what it was awaited with.
    contributor = ContentContributor("fake", "A fake contributor", {"open-edx": AsyncMock(wraps=build_fake)})
    register_content_contributor(contributor)
    return contributor


def add_args(contributor: str = "fake") -> AddPluginContentArgs:
    return AddPluginContentArgs(
        auth=AUTH,
        course_id="course-v1:X+Y+Z",
        unit_locator="block-v1:X+Y+Z+type@vertical+block@u1",
        contributor=contributor,
    )


async def test_lists_the_registered_contributors(fake_contributor: ContentContributor) -> None:
    result = await openedx_list_content_contributors()

    assert {"name": "fake", "description": "A fake contributor"} in result["response"]["contributors"]


async def test_creates_the_block_the_contributor_declares(fake_contributor: ContentContributor) -> None:
    with (
        patch(
            "sparkth.plugins.openedx.tools.openedx_create_basic_component",
            new=AsyncMock(return_value="block-v1:X+Y+Z+type@fake+block@b1"),
        ) as create,
        patch(
            "sparkth.plugins.openedx.tools.openedx_update_xblock_content",
            new=AsyncMock(return_value={"ok": True}),
        ) as update,
    ):
        result = await openedx_add_plugin_content(add_args())

    cast(AsyncMock, fake_contributor.builders["open-edx"]).assert_awaited_once_with("course-v1:X+Y+Z")
    create.assert_awaited_once_with(
        AUTH, "course-v1:X+Y+Z", "block-v1:X+Y+Z+type@vertical+block@u1", "fake", "Fake Activity"
    )
    update.assert_awaited_once_with(
        AUTH,
        "course-v1:X+Y+Z",
        "block-v1:X+Y+Z+type@fake+block@b1",
        None,
        {"placement": "p-1", "activity": "mcq"},
    )
    assert result["response"]["locator"] == "block-v1:X+Y+Z+type@fake+block@b1"
    assert result["response"]["category"] == "fake"


async def test_unknown_contributor_is_an_error_and_creates_nothing() -> None:
    with patch("sparkth.plugins.openedx.tools.openedx_create_basic_component", new=AsyncMock()) as create:
        result = await openedx_add_plugin_content(add_args("absent"))

    create.assert_not_awaited()
    assert "absent" in result["error"]["message"]


async def test_a_studio_failure_is_reported_as_an_error_dict(fake_contributor: ContentContributor) -> None:
    failure = LMSRequestError(Method.POST, "api/contentstore/v0/xblock/course-v1:X+Y+Z", 403, "Forbidden")
    with patch(
        "sparkth.plugins.openedx.tools.openedx_create_basic_component",
        new=AsyncMock(side_effect=failure),
    ):
        result = await openedx_add_plugin_content(add_args())

    assert result["error"]["status_code"] == 403


async def build_broken(course_id: str) -> ContentBlock:
    raise ContentBuildError("disk full")


async def test_a_build_failure_is_reported_as_an_error_dict_and_creates_nothing() -> None:
    broken = ContentContributor("broken", "A contributor that cannot build", {"open-edx": build_broken})
    register_content_contributor(broken)

    with patch("sparkth.plugins.openedx.tools.openedx_create_basic_component", new=AsyncMock()) as create:
        result = await openedx_add_plugin_content(add_args("broken"))

    create.assert_not_awaited()
    assert "broken" in result["error"]["message"]
    assert "disk full" in result["error"]["message"]


async def build_fake_without_attributes(course_id: str) -> ContentBlock:
    return ContentBlock("Fake Activity", "fake", {})


async def test_a_block_with_no_attributes_skips_the_update_call() -> None:
    bare = ContentContributor("bare", "A contributor with no attributes", {"open-edx": build_fake_without_attributes})
    register_content_contributor(bare)

    with (
        patch(
            "sparkth.plugins.openedx.tools.openedx_create_basic_component",
            new=AsyncMock(return_value="block-v1:X+Y+Z+type@fake+block@b1"),
        ) as create,
        patch(
            "sparkth.plugins.openedx.tools.openedx_update_xblock_content",
            new=AsyncMock(),
        ) as update,
    ):
        result = await openedx_add_plugin_content(add_args("bare"))

    create.assert_awaited_once()
    update.assert_not_awaited()
    assert result["response"]["locator"] == "block-v1:X+Y+Z+type@fake+block@b1"
    assert result["response"]["category"] == "fake"


async def build_canvas_only(course_id: str) -> ContentBlock:
    return ContentBlock("Canvas Only", "Page", "<p>hi</p>")


def _register_canvas_only() -> ContentContributor:
    contributor = ContentContributor("canvas-only", "A canvas contributor", {"canvas": build_canvas_only})
    register_content_contributor(contributor)
    return contributor


async def test_a_contributor_with_no_openedx_builder_is_not_listed(fake_contributor: ContentContributor) -> None:
    """A contributor targeting another LMS must not be offered to an agent publishing here."""
    _register_canvas_only()

    result = await openedx_list_content_contributors()

    names = [entry["name"] for entry in result["response"]["contributors"]]
    assert "fake" in names
    assert "canvas-only" not in names


async def test_a_contributor_with_no_openedx_builder_is_refused_and_creates_nothing() -> None:
    """Listing is not the only entry point: the name can be passed to this tool directly."""
    _register_canvas_only()

    with patch("sparkth.plugins.openedx.tools.openedx_create_basic_component", new=AsyncMock()) as create:
        result = await openedx_add_plugin_content(add_args("canvas-only"))

    create.assert_not_awaited()
    assert "canvas-only" in result["error"]["message"]


async def test_a_contributor_that_targets_nothing_is_refused_and_creates_nothing() -> None:
    """An empty builders map registers cleanly, so this tool is what has to refuse it."""
    register_content_contributor(ContentContributor("no-targets", "A contributor with no builders", {}))

    with patch("sparkth.plugins.openedx.tools.openedx_create_basic_component", new=AsyncMock()) as create:
        result = await openedx_add_plugin_content(add_args("no-targets"))

    create.assert_not_awaited()
    assert "no-targets" in result["error"]["message"]
