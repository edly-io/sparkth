from unittest.mock import AsyncMock, patch

import pytest

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
    contributor = ContentContributor("fake", "A fake contributor", build_fake)
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
