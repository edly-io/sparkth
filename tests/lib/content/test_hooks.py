from collections.abc import Iterator

import pytest

from sparkth.lib.content.exceptions import DuplicateContentContributorError
from sparkth.lib.content.hooks import (
    LMS_CONTENT_CONTRIBUTORS,
    ContentBlock,
    ContentContributor,
    register_content_contributor,
)


async def build_openedx_stub(course_id: str) -> ContentBlock:
    return ContentBlock("A Stub", "stub", {"course": course_id})


async def build_canvas_stub(course_id: str) -> ContentBlock:
    return ContentBlock("A Stub", "Page", f"<p>{course_id}</p>")


def _stub_contributor() -> ContentContributor:
    return ContentContributor(
        "stub",
        "A stub contributor",
        {"open-edx": build_openedx_stub, "canvas": build_canvas_stub},
    )


@pytest.fixture
def registered() -> Iterator[ContentContributor]:
    contributor = _stub_contributor()
    register_content_contributor(contributor)
    yield contributor
    LMS_CONTENT_CONTRIBUTORS.remove("stub")


async def test_registered_contributor_is_resolved_by_name(registered: ContentContributor) -> None:
    assert LMS_CONTENT_CONTRIBUTORS.get("stub") is registered


async def test_unregistered_name_resolves_to_none() -> None:
    assert LMS_CONTENT_CONTRIBUTORS.get("absent") is None


async def test_each_target_builds_the_block_that_target_expects(registered: ContentContributor) -> None:
    """The point of a builder per target: one contributor, a differently shaped block per LMS."""
    contributor = LMS_CONTENT_CONTRIBUTORS.get("stub")
    assert contributor is not None

    for_openedx = await contributor.builders["open-edx"]("course-v1:X+Y+Z")
    for_canvas = await contributor.builders["canvas"]("course-v1:X+Y+Z")

    assert (for_openedx.title, for_openedx.kind) == ("A Stub", "stub")
    assert for_openedx.attributes == {"course": "course-v1:X+Y+Z"}
    assert (for_canvas.title, for_canvas.kind) == ("A Stub", "Page")
    assert for_canvas.attributes == "<p>course-v1:X+Y+Z</p>"


async def test_a_second_contributor_claiming_the_name_is_rejected(registered: ContentContributor) -> None:
    with pytest.raises(DuplicateContentContributorError, match="stub"):
        register_content_contributor(ContentContributor("stub", "Another", {"open-edx": build_openedx_stub}))


async def test_a_contributor_targeting_fewer_lmses_under_the_same_name_is_rejected(
    registered: ContentContributor,
) -> None:
    """``builders`` is now the discriminator: same name and description, fewer targets, unequal."""
    with pytest.raises(DuplicateContentContributorError, match="stub"):
        register_content_contributor(ContentContributor("stub", "A stub contributor", {"open-edx": build_openedx_stub}))


async def test_re_registering_an_equal_contributor_keeps_the_first(registered: ContentContributor) -> None:
    # The plugin owning a contributor is constructed more than once in one process — by the
    # loader and again by its own tests — so each construction re-registers the same value.
    register_content_contributor(_stub_contributor())

    assert LMS_CONTENT_CONTRIBUTORS.get("stub") is registered
