from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from sparkth.lib.content.exceptions import ContentBuildError
from sparkth.lib.content.hooks import LMS_CONTENT_CONTRIBUTORS, ContentBlock, ContentContributor
from sparkth.lib.enums import Method
from sparkth.lib.exceptions import LMSRequestError
from sparkth.plugins.openedx.schemas import AccessTokenPayload, AddPluginContentArgs
from sparkth.plugins.openedx.tools import openedx_add_plugin_content, openedx_list_content_contributors

AUTH = AccessTokenPayload(access_token="t", lms_url="https://lms", studio_url="https://studio")


async def build_fake(course_id: str) -> ContentBlock:
    return ContentBlock("fake", "Fake Activity", {"placement": "p-1", "activity": "mcq"})


@pytest.fixture
def fake_contributor(monkeypatch: pytest.MonkeyPatch) -> ContentContributor:
    # Wraps (rather than replaces) build_fake so tests can assert what it was awaited with.
    contributor = ContentContributor("fake", "A fake contributor", AsyncMock(wraps=build_fake))
    monkeypatch.setitem(LMS_CONTENT_CONTRIBUTORS._items, "fake", contributor)
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

    cast(AsyncMock, fake_contributor.build).assert_awaited_once_with("course-v1:X+Y+Z")
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


async def test_a_build_failure_is_reported_as_an_error_dict_and_creates_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broken = ContentContributor("broken", "A contributor that cannot build", build_broken)
    monkeypatch.setitem(LMS_CONTENT_CONTRIBUTORS._items, "broken", broken)

    with patch("sparkth.plugins.openedx.tools.openedx_create_basic_component", new=AsyncMock()) as create:
        result = await openedx_add_plugin_content(add_args("broken"))

    create.assert_not_awaited()
    assert "broken" in result["error"]["message"]
    assert "disk full" in result["error"]["message"]


async def build_fake_without_settings(course_id: str) -> ContentBlock:
    return ContentBlock("fake", "Fake Activity", {})


async def test_a_block_with_no_settings_skips_the_update_call(monkeypatch: pytest.MonkeyPatch) -> None:
    bare = ContentContributor("bare", "A contributor with no settings", build_fake_without_settings)
    monkeypatch.setitem(LMS_CONTENT_CONTRIBUTORS._items, "bare", bare)

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
