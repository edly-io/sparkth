from collections.abc import Iterator

import pytest

from sparkth.lib.content.exceptions import DuplicateContentContributorError
from sparkth.lib.content.hooks import (
    LMS_CONTENT_CONTRIBUTORS,
    ContentBlock,
    ContentContributor,
    register_content_contributor,
)


async def build_stub(course_id: str) -> ContentBlock:
    return ContentBlock("stub", "A Stub", {"course": course_id})


@pytest.fixture
def registered() -> Iterator[ContentContributor]:
    contributor = ContentContributor("stub", "A stub contributor", build_stub)
    register_content_contributor(contributor)
    yield contributor
    LMS_CONTENT_CONTRIBUTORS.remove("stub")


async def test_registered_contributor_is_resolved_by_name(registered: ContentContributor) -> None:
    assert LMS_CONTENT_CONTRIBUTORS.get("stub") is registered


async def test_unregistered_name_resolves_to_none() -> None:
    assert LMS_CONTENT_CONTRIBUTORS.get("absent") is None


async def test_build_returns_the_block_the_contributor_declares(registered: ContentContributor) -> None:
    contributor = LMS_CONTENT_CONTRIBUTORS.get("stub")
    assert contributor is not None
    block = await contributor.build("course-v1:X+Y+Z")

    assert block.category == "stub"
    assert block.display_name == "A Stub"
    assert block.settings == {"course": "course-v1:X+Y+Z"}


async def test_a_second_contributor_claiming_the_name_is_rejected(registered: ContentContributor) -> None:
    with pytest.raises(DuplicateContentContributorError, match="stub"):
        register_content_contributor(ContentContributor("stub", "Another", build_stub))


async def test_re_registering_an_equal_contributor_keeps_the_first(registered: ContentContributor) -> None:
    # The plugin owning a contributor is constructed more than once in one process — by the
    # loader and again by its own tests — so each construction re-registers the same value.
    register_content_contributor(ContentContributor("stub", "A stub contributor", build_stub))

    assert LMS_CONTENT_CONTRIBUTORS.get("stub") is registered
