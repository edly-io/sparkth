"""Authored content reaches learners only when the author publishes the course."""

from collections.abc import Iterator
from unittest.mock import AsyncMock, call, patch

import pytest

from sparkth.lib.enums import Method
from sparkth.lib.exceptions import LMSRequestError
from sparkth.plugins.openedx.schemas import AccessTokenPayload, CreateCourseArgs, PublishContentArgs
from sparkth.plugins.openedx.tools import (
    openedx_create_course_run,
    openedx_publish_content,
    openedx_update_xblock_content,
)

AUTH = AccessTokenPayload(access_token="t", lms_url="https://lms", studio_url="https://studio")
COURSE_ID = "course-v1:Org+101+2026"
UNIT = "block-v1:Org+101+2026+type@vertical+block@u1"
UNIT_ENDPOINT = f"api/contentstore/v0/xblock/{COURSE_ID}/block-v1%3AOrg%2B101%2B2026%2Btype%40vertical%2Bblock%40u1"
COURSE_BLOCK = "block-v1:Org+101+2026+type@course+block@course"
COURSE_BLOCK_ENDPOINT = (
    f"api/contentstore/v0/xblock/{COURSE_ID}/block-v1%3AOrg%2B101%2B2026%2Btype%40course%2Bblock%40course"
)


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


def course_args() -> CreateCourseArgs:
    return CreateCourseArgs(auth=AUTH, org="Org", number="101", run="2026", title="A course", pacing_type="self_paced")


async def test_a_new_course_is_hidden_from_learners(studio_client: AsyncMock) -> None:
    """Sections and subsections publish the moment they are created, so without this gate the
    skeleton of a course reaches learners while the author is still writing it."""
    studio_client.post.return_value = {"id": COURSE_ID}
    studio_client.patch.return_value = {"id": COURSE_BLOCK}

    result = await openedx_create_course_run(course_args())

    assert studio_client.patch.await_args == call(
        "https://studio", COURSE_BLOCK_ENDPOINT, {"metadata": {"visible_to_staff_only": True}}
    )
    assert result["hidden_from_learners"] is True


async def test_a_course_that_could_not_be_hidden_says_so(studio_client: AsyncMock) -> None:
    """The course exists either way, so the author is told its real state rather than being left
    to assume the work is private."""
    studio_client.post.return_value = {"id": COURSE_ID}
    studio_client.patch.side_effect = LMSRequestError(Method.PATCH, COURSE_BLOCK_ENDPOINT, 403, "Forbidden")

    result = await openedx_create_course_run(course_args())

    assert result["response"] == {"id": COURSE_ID}
    assert result["hidden_from_learners"] is False


async def test_publishing_the_course_opens_it_to_learners(studio_client: AsyncMock) -> None:
    """Publishing the course is the author's release: it lifts the gate and releases the drafts
    in one request, so learners never see a half-open course."""
    studio_client.patch.return_value = {"id": COURSE_BLOCK}

    await openedx_publish_content(publish_args(COURSE_BLOCK))

    assert studio_client.patch.await_args == call(
        "https://studio",
        COURSE_BLOCK_ENDPOINT,
        {"metadata": {"visible_to_staff_only": False}, "publish": "make_public"},
    )


async def test_publishing_one_unit_leaves_the_course_gate_closed(studio_client: AsyncMock) -> None:
    """Releasing the course is a decision of its own; publishing a part of it must not make it."""
    studio_client.patch.return_value = {"id": UNIT}

    await openedx_publish_content(publish_args())

    assert studio_client.patch.await_args == call("https://studio", UNIT_ENDPOINT, {"publish": "make_public"})
