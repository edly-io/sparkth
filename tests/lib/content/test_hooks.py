from collections.abc import Iterator

import pytest

from sparkth.lib.content.hooks import LMS_CONTENT_CONTRIBUTORS, ContentBlock, ContentContributor


async def build_stub(course_id: str) -> ContentBlock:
    return ContentBlock("stub", "A Stub", {"course": course_id})


@pytest.fixture
def registered() -> Iterator[ContentContributor]:
    contributor = ContentContributor("stub", "A stub contributor", build_stub)
    LMS_CONTENT_CONTRIBUTORS.add_item(contributor)
    yield contributor
    # No public remove() on SingleNamedItemHook; private access is the only teardown available.
    LMS_CONTENT_CONTRIBUTORS._items.pop("stub", None)


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
    with pytest.raises(ValueError, match="Duplicate hook item: stub"):
        LMS_CONTENT_CONTRIBUTORS.add_item(ContentContributor("stub", "Another", build_stub))
