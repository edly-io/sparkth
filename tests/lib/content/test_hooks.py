import gc
from collections.abc import Iterator
from typing import cast

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.plugin import Plugin, UserPlugin
from sparkth.core.models.user import User
from sparkth.lib.auth import bind_current_user_id, current_user_id
from sparkth.lib.content.exceptions import (
    ContentContributorUnavailableError,
    DuplicateContentContributorError,
    UnknownContentContributorError,
)
from sparkth.lib.content.hooks import (
    ContentBlock,
    ContentContributor,
    ContentOption,
    enabled_content_contributor,
    enabled_content_contributors,
    register_content_contributor,
)
from sparkth.lib.exceptions.auth import NoAuthenticatedUser
from sparkth.lib.plugins import SparkthPlugin


async def build_openedx_stub(course_id: str, option_id: str | None) -> ContentBlock:
    return ContentBlock("A Stub", "stub", {"course": course_id})


async def build_canvas_stub(course_id: str, option_id: str | None) -> ContentBlock:
    return ContentBlock("A Stub", "Page", f"<p>{course_id}</p>")


def _stub_contributor() -> ContentContributor:
    return ContentContributor(
        "stub",
        "A stub contributor",
        {"open-edx": build_openedx_stub, "canvas": build_canvas_stub},
    )


@pytest.fixture
def owner() -> Iterator[SparkthPlugin]:
    """The plugin owning the stub contributor, which the hook holds only while the test does."""
    plugin = SparkthPlugin("stub-owner")
    yield plugin
    del plugin
    gc.collect()


@pytest.fixture
def registered(owner: SparkthPlugin) -> ContentContributor:
    contributor = _stub_contributor()
    register_content_contributor(owner, contributor)
    return contributor


async def test_registered_contributor_is_resolved_by_name(
    registered: ContentContributor, session: AsyncSession
) -> None:
    assert await enabled_content_contributor("stub") is registered


async def test_an_unregistered_name_is_unknown() -> None:
    with pytest.raises(UnknownContentContributorError, match="absent"):
        await enabled_content_contributor("absent")


async def test_a_contributor_goes_once_its_plugin_is_collected() -> None:
    plugin = SparkthPlugin("stub-owner")
    register_content_contributor(plugin, _stub_contributor())

    del plugin
    gc.collect()

    with pytest.raises(UnknownContentContributorError):
        await enabled_content_contributor("stub")


async def test_each_target_builds_the_block_that_target_expects(registered: ContentContributor) -> None:
    """The point of a builder per target: one contributor, a differently shaped block per LMS."""
    for_openedx = await registered.builders["open-edx"]("course-v1:X+Y+Z", None)
    for_canvas = await registered.builders["canvas"]("course-v1:X+Y+Z", None)

    assert (for_openedx.title, for_openedx.kind) == ("A Stub", "stub")
    assert for_openedx.attributes == {"course": "course-v1:X+Y+Z"}
    assert (for_canvas.title, for_canvas.kind) == ("A Stub", "Page")
    assert for_canvas.attributes == "<p>course-v1:X+Y+Z</p>"


async def test_a_second_contributor_claiming_the_name_is_rejected(
    registered: ContentContributor, owner: SparkthPlugin
) -> None:
    with pytest.raises(DuplicateContentContributorError, match="stub"):
        register_content_contributor(owner, ContentContributor("stub", "Another", {"open-edx": build_openedx_stub}))


async def test_another_plugin_claiming_the_name_is_rejected_even_with_an_equal_contributor(
    registered: ContentContributor,
) -> None:
    # The value cannot tell the owners apart, so it could not say whose switch applies.
    other = SparkthPlugin("other-owner")

    with pytest.raises(DuplicateContentContributorError, match="stub"):
        register_content_contributor(other, _stub_contributor())


async def test_a_contributor_targeting_fewer_lmses_under_the_same_name_is_rejected(
    registered: ContentContributor, owner: SparkthPlugin
) -> None:
    """``builders`` is now the discriminator: same name and description, fewer targets, unequal."""
    with pytest.raises(DuplicateContentContributorError, match="stub"):
        register_content_contributor(
            owner, ContentContributor("stub", "A stub contributor", {"open-edx": build_openedx_stub})
        )


async def test_another_construction_registering_an_equal_contributor_is_accepted(
    registered: ContentContributor, session: AsyncSession
) -> None:
    # The plugin owning a contributor is constructed more than once in one process — by the
    # loader and again by its own tests — so each construction registers the same value again.
    again = SparkthPlugin("stub-owner")
    register_content_contributor(again, _stub_contributor())

    assert await enabled_content_contributor("stub") == registered


async def list_stub_options() -> list[ContentOption]:
    return [ContentOption("one", "One")]


async def test_a_contributor_adding_options_under_the_same_name_is_rejected(
    registered: ContentContributor, owner: SparkthPlugin
) -> None:
    """Options are part of a contributor's identity, like its builders."""
    with pytest.raises(DuplicateContentContributorError) as caught:
        register_content_contributor(
            owner,
            ContentContributor(
                "stub",
                "A stub contributor",
                {"open-edx": build_openedx_stub, "canvas": build_canvas_stub},
                list_stub_options,
            ),
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
    await _seed_owner(session, False)
    await _seed_user(session)
    bind_current_user_id(1)

    assert "stub" not in await enabled_content_contributors()


async def test_with_no_bound_user_only_the_system_switch_applies(
    registered: ContentContributor, session: AsyncSession
) -> None:
    with pytest.raises(NoAuthenticatedUser):  # precondition: no user leaked from another test
        current_user_id()
    await _seed_owner(session, False)

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


async def test_a_named_contributor_whose_plugin_is_off_system_wide_is_unavailable(
    registered: ContentContributor, session: AsyncSession
) -> None:
    await _seed_owner(session, False)

    with pytest.raises(ContentContributorUnavailableError, match="stub"):
        await enabled_content_contributor("stub")


async def test_a_named_contributor_whose_plugin_the_user_switched_off_is_unavailable(
    registered: ContentContributor, session: AsyncSession
) -> None:
    plugin = await _seed_owner(session)
    user = await _seed_user(session)
    session.add(UserPlugin(user_id=cast(int, user.id), plugin_id=cast(int, plugin.id), enabled=False))
    await session.commit()
    bind_current_user_id(1)

    with pytest.raises(ContentContributorUnavailableError, match="stub"):
        await enabled_content_contributor("stub")
