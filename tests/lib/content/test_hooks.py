from collections.abc import Iterator
from typing import cast

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.plugin import Plugin, UserPlugin
from sparkth.core.models.user import User
from sparkth.lib.auth import bind_current_user_id, current_user_id
from sparkth.lib.content.exceptions import DuplicateContentContributorError
from sparkth.lib.content.hooks import (
    LMS_CONTENT_CONTRIBUTORS,
    ContentBlock,
    ContentContributor,
    ContentOption,
    enabled_content_contributors,
    register_content_contributor,
)
from sparkth.lib.exceptions.auth import NoAuthenticatedUser


async def build_openedx_stub(course_id: str, option_id: str | None) -> ContentBlock:
    return ContentBlock("A Stub", "stub", {"course": course_id})


async def build_canvas_stub(course_id: str, option_id: str | None) -> ContentBlock:
    return ContentBlock("A Stub", "Page", f"<p>{course_id}</p>")


def _stub_contributor() -> ContentContributor:
    return ContentContributor(
        "stub",
        "A stub contributor",
        {"open-edx": build_openedx_stub, "canvas": build_canvas_stub},
        plugin_name="stub-owner",
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

    for_openedx = await contributor.builders["open-edx"]("course-v1:X+Y+Z", None)
    for_canvas = await contributor.builders["canvas"]("course-v1:X+Y+Z", None)

    assert (for_openedx.title, for_openedx.kind) == ("A Stub", "stub")
    assert for_openedx.attributes == {"course": "course-v1:X+Y+Z"}
    assert (for_canvas.title, for_canvas.kind) == ("A Stub", "Page")
    assert for_canvas.attributes == "<p>course-v1:X+Y+Z</p>"


async def test_a_second_contributor_claiming_the_name_is_rejected(registered: ContentContributor) -> None:
    with pytest.raises(DuplicateContentContributorError, match="stub"):
        register_content_contributor(
            ContentContributor("stub", "Another", {"open-edx": build_openedx_stub}, plugin_name="stub-owner")
        )


async def test_a_contributor_targeting_fewer_lmses_under_the_same_name_is_rejected(
    registered: ContentContributor,
) -> None:
    """``builders`` is now the discriminator: same name and description, fewer targets, unequal."""
    with pytest.raises(DuplicateContentContributorError, match="stub"):
        register_content_contributor(
            ContentContributor("stub", "A stub contributor", {"open-edx": build_openedx_stub}, plugin_name="stub-owner")
        )


async def test_re_registering_an_equal_contributor_keeps_the_first(registered: ContentContributor) -> None:
    # The plugin owning a contributor is constructed more than once in one process — by the
    # loader and again by its own tests — so each construction re-registers the same value.
    register_content_contributor(_stub_contributor())

    assert LMS_CONTENT_CONTRIBUTORS.get("stub") is registered


async def list_stub_options() -> list[ContentOption]:
    return [ContentOption("one", "One")]


async def test_a_contributor_adding_options_under_the_same_name_is_rejected(
    registered: ContentContributor,
) -> None:
    """Options are part of a contributor's identity, like its builders."""
    with pytest.raises(DuplicateContentContributorError) as caught:
        register_content_contributor(
            ContentContributor(
                "stub",
                "A stub contributor",
                {"open-edx": build_openedx_stub, "canvas": build_canvas_stub},
                list_stub_options,
                plugin_name="stub-owner",
            )
        )

    assert caught.value.name == "stub"


async def _seed_owner(session: AsyncSession, enabled: bool = True) -> Plugin:
    plugin = Plugin(name="stub-owner", enabled=enabled)
    session.add(plugin)
    await session.commit()
    await session.refresh(plugin)
    return plugin


async def _seed_user(session: AsyncSession) -> User:
    user = User(id=1, name="U", username="u", email="u@example.com", hashed_password="x")
    session.add(user)
    await session.commit()
    return user


async def test_a_contributor_of_an_enabled_plugin_is_offered(
    registered: ContentContributor, session: AsyncSession
) -> None:
    assert (await enabled_content_contributors())["stub"] is registered


async def test_a_contributor_whose_plugin_the_user_switched_off_is_withheld(
    registered: ContentContributor, session: AsyncSession
) -> None:
    plugin = await _seed_owner(session)
    user = await _seed_user(session)
    session.add(UserPlugin(user_id=cast(int, user.id), plugin_id=cast(int, plugin.id), enabled=False))
    await session.commit()
    bind_current_user_id(1)

    assert "stub" not in await enabled_content_contributors()


async def test_a_contributor_whose_plugin_is_off_system_wide_is_withheld(
    registered: ContentContributor, session: AsyncSession
) -> None:
    await _seed_owner(session, enabled=False)
    await _seed_user(session)
    bind_current_user_id(1)

    assert "stub" not in await enabled_content_contributors()


async def test_with_no_bound_user_only_the_system_switch_applies(
    registered: ContentContributor, session: AsyncSession
) -> None:
    with pytest.raises(NoAuthenticatedUser):  # precondition: no user leaked from another test
        current_user_id()
    await _seed_owner(session, enabled=False)

    assert "stub" not in await enabled_content_contributors()


async def test_with_no_bound_user_a_users_preference_has_no_effect(
    registered: ContentContributor, session: AsyncSession
) -> None:
    with pytest.raises(NoAuthenticatedUser):
        current_user_id()
    plugin = await _seed_owner(session)
    user = await _seed_user(session)
    session.add(UserPlugin(user_id=cast(int, user.id), plugin_id=cast(int, plugin.id), enabled=False))
    await session.commit()

    assert "stub" in await enabled_content_contributors()
