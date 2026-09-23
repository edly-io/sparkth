"""Publishing is the separate step that makes authored content visible to learners."""

from collections.abc import Iterator
from unittest.mock import AsyncMock, call, patch

import pytest

from sparkth.lib.enums import Method
from sparkth.lib.exceptions import LMSRequestError
from sparkth.plugins.openedx.schemas import AccessTokenPayload, PublishContentArgs
from sparkth.plugins.openedx.tools import openedx_publish_content, openedx_update_xblock_content

AUTH = AccessTokenPayload(access_token="t", lms_url="https://lms", studio_url="https://studio")
COURSE_ID = "course-v1:Org+101+2026"
UNIT = "block-v1:Org+101+2026+type@vertical+block@u1"
UNIT_ENDPOINT = f"api/contentstore/v0/xblock/{COURSE_ID}/block-v1%3AOrg%2B101%2B2026%2Btype%40vertical%2Bblock%40u1"


@pytest.fixture
def studio_client() -> Iterator[AsyncMock]:
    with patch("sparkth.plugins.openedx.tools.OpenEdxClient") as mock_cls:
        client = AsyncMock()
        mock_cls.return_value.__aenter__.return_value = client
        mock_cls.return_value.__aexit__.return_value = None
        yield client


def publish_args(locator: str = UNIT) -> PublishContentArgs:
    return PublishContentArgs(auth=AUTH, course_id=COURSE_ID, locator=locator)


async def test_publishing_asks_studio_to_make_the_block_public(studio_client: AsyncMock) -> None:
    studio_client.patch.return_value = {"id": UNIT}

    await openedx_publish_content(publish_args())

    assert studio_client.patch.await_args == call("https://studio", UNIT_ENDPOINT, {"publish": "make_public"})


async def test_the_author_is_told_which_block_was_published(studio_client: AsyncMock) -> None:
    studio_client.patch.return_value = {"id": UNIT}

    result = await openedx_publish_content(publish_args())

    assert result["response"]["locator"] == UNIT


async def test_a_refused_publish_is_reported_as_a_failure(studio_client: AsyncMock) -> None:
    """An account that may author but not publish gets a 403, which must not read as success."""
    studio_client.patch.side_effect = LMSRequestError(Method.PATCH, UNIT_ENDPOINT, 403, "Forbidden")

    result = await openedx_publish_content(publish_args())

    assert "response" not in result
    assert result["error"]["status_code"] == 403
    assert result["error"]["locator"] == UNIT


async def test_an_update_that_changes_nothing_is_still_refused(studio_client: AsyncMock) -> None:
    """Publishing is the only reason to send a body with no content, so the guard still holds."""
    with pytest.raises(LMSRequestError):
        await openedx_update_xblock_content(AUTH, COURSE_ID, UNIT, None, None)

    studio_client.patch.assert_not_awaited()
