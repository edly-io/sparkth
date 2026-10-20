import gc
from collections.abc import Iterator
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.plugin import Plugin, UserPlugin
from sparkth.core.models.user import User
from sparkth.lib.auth import bind_current_user_id
from sparkth.lib.content.exceptions import ContentBuildError, ContentPlacementError
from sparkth.lib.content.hooks import (
    ContentBlock,
    ContentContributor,
    ContentOption,
    register_content_contributor,
)
from sparkth.lib.enums import Method
from sparkth.lib.exceptions import LMSRequestError
from sparkth.lib.plugins import SparkthPlugin
from sparkth.plugins.openedx.schemas import AccessTokenPayload, AddPluginContentArgs
from sparkth.plugins.openedx.tools import openedx_add_plugin_content, openedx_list_content_contributors

AUTH = AccessTokenPayload(access_token="t", lms_url="https://lms", studio_url="https://studio")


async def build_fake(course_id: str, option_id: str | None) -> ContentBlock:
    return ContentBlock("Fake Activity", "fake", {"activity_instance": "p-1", "activity": "mcq"})


@pytest.fixture
def owners() -> Iterator[list[SparkthPlugin]]:
    """The plugins owning this test's contributors.

    The hook holds each plugin weakly, so its contributor stays registered while the plugin is
    held here and goes once the test drops it: one test's contributor is never listed by the next.
    """
    plugins: list[SparkthPlugin] = []
    yield plugins
    plugins.clear()
    gc.collect()


def _register(
    owners: list[SparkthPlugin], contributor: ContentContributor, plugin_name: str = "stub-owner"
) -> ContentContributor:
    """Register ``contributor`` under a new plugin named ``plugin_name``, held by ``owners``."""
    plugin = SparkthPlugin(plugin_name)
    owners.append(plugin)
    register_content_contributor(plugin, contributor)
    return contributor


@pytest.fixture
def fake_contributor(owners: list[SparkthPlugin]) -> ContentContributor:
    # Wraps (rather than replaces) build_fake so tests can assert what it was awaited with.
    return _register(
        owners, ContentContributor("fake", "A fake contributor", {"open-edx": AsyncMock(wraps=build_fake)})
    )


def add_args(contributor: str = "fake", option_id: str | None = None) -> AddPluginContentArgs:
    return AddPluginContentArgs(
        auth=AUTH,
        course_id="course-v1:X+Y+Z",
        unit_locator="block-v1:X+Y+Z+type@vertical+block@u1",
        contributor=contributor,
        option_id=option_id,
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

    cast(AsyncMock, fake_contributor.builders["open-edx"]).assert_awaited_once_with("course-v1:X+Y+Z", None)
    create.assert_awaited_once_with(
        AUTH, "course-v1:X+Y+Z", "block-v1:X+Y+Z+type@vertical+block@u1", "fake", "Fake Activity"
    )
    update.assert_awaited_once_with(
        AUTH,
        "course-v1:X+Y+Z",
        "block-v1:X+Y+Z+type@fake+block@b1",
        None,
        {"activity_instance": "p-1", "activity": "mcq"},
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


async def build_broken(course_id: str, option_id: str | None) -> ContentBlock:
    raise ContentBuildError("disk full")


async def test_a_build_failure_is_reported_as_an_error_dict_and_creates_nothing(owners: list[SparkthPlugin]) -> None:
    _register(owners, ContentContributor("broken", "A contributor that cannot build", {"open-edx": build_broken}))

    with patch("sparkth.plugins.openedx.tools.openedx_create_basic_component", new=AsyncMock()) as create:
        result = await openedx_add_plugin_content(add_args("broken"))

    create.assert_not_awaited()
    assert "broken" in result["error"]["message"]
    assert "disk full" in result["error"]["message"]


async def build_fake_without_attributes(course_id: str, option_id: str | None) -> ContentBlock:
    return ContentBlock("Fake Activity", "fake", {})


async def test_a_block_with_no_attributes_skips_the_update_call(owners: list[SparkthPlugin]) -> None:
    _register(
        owners,
        ContentContributor("bare", "A contributor with no attributes", {"open-edx": build_fake_without_attributes}),
    )

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


async def build_canvas_only(course_id: str, option_id: str | None) -> ContentBlock:
    return ContentBlock("Canvas Only", "Page", "<p>hi</p>")


def _register_canvas_only(owners: list[SparkthPlugin]) -> ContentContributor:
    return _register(owners, ContentContributor("canvas-only", "A canvas contributor", {"canvas": build_canvas_only}))


async def test_a_contributor_with_no_openedx_builder_is_not_listed(
    fake_contributor: ContentContributor, owners: list[SparkthPlugin]
) -> None:
    """A contributor targeting another LMS must not be offered to an agent publishing here."""
    _register_canvas_only(owners)

    result = await openedx_list_content_contributors()

    names = [entry["name"] for entry in result["response"]["contributors"]]
    assert "fake" in names
    assert "canvas-only" not in names


async def test_a_contributor_with_no_openedx_builder_is_refused_and_creates_nothing(
    owners: list[SparkthPlugin],
) -> None:
    """Listing is not the only entry point: the name can be passed to this tool directly."""
    _register_canvas_only(owners)

    with patch("sparkth.plugins.openedx.tools.openedx_create_basic_component", new=AsyncMock()) as create:
        result = await openedx_add_plugin_content(add_args("canvas-only"))

    create.assert_not_awaited()
    assert "canvas-only" in result["error"]["message"]


async def test_a_contributor_that_targets_nothing_is_refused_and_creates_nothing(
    owners: list[SparkthPlugin],
) -> None:
    """An empty builders map registers cleanly, so this tool is what has to refuse it."""
    _register(owners, ContentContributor("no-targets", "A contributor with no builders", {}))

    with patch("sparkth.plugins.openedx.tools.openedx_create_basic_component", new=AsyncMock()) as create:
        result = await openedx_add_plugin_content(add_args("no-targets"))

    create.assert_not_awaited()
    assert "no-targets" in result["error"]["message"]


async def test_a_failed_attribute_patch_reports_the_locator_it_created(fake_contributor: ContentContributor) -> None:
    """The block already exists in Studio by then, so the caller needs its locator to act on it."""
    failure = LMSRequestError(Method.PATCH, "api/contentstore/v0/xblock/course-v1:X+Y+Z", 500, "Boom")
    with (
        patch(
            "sparkth.plugins.openedx.tools.openedx_create_basic_component",
            new=AsyncMock(return_value="block-v1:X+Y+Z+type@fake+block@b1"),
        ),
        patch("sparkth.plugins.openedx.tools.openedx_update_xblock_content", new=AsyncMock(side_effect=failure)),
    ):
        result = await openedx_add_plugin_content(add_args())

    assert result["error"]["status_code"] == 500
    assert result["error"]["locator"] == "block-v1:X+Y+Z+type@fake+block@b1"


async def test_a_failed_create_reports_no_locator(fake_contributor: ContentContributor) -> None:
    """Nothing was created, so there is nothing for the caller to clean up."""
    failure = LMSRequestError(Method.POST, "api/contentstore/v0/xblock/course-v1:X+Y+Z", 403, "Forbidden")
    with patch("sparkth.plugins.openedx.tools.openedx_create_basic_component", new=AsyncMock(side_effect=failure)):
        result = await openedx_add_plugin_content(add_args())

    assert "locator" not in result["error"]


async def list_fake_options() -> list[ContentOption]:
    return [ContentOption("first", "The first one"), ContentOption("second", "The second one")]


@pytest.fixture
def optioned_contributor(owners: list[SparkthPlugin]) -> ContentContributor:
    return _register(
        owners,
        ContentContributor(
            "optioned", "A contributor with options", {"open-edx": AsyncMock(wraps=build_fake)}, list_fake_options
        ),
    )


async def test_a_contributor_with_options_lists_them(optioned_contributor: ContentContributor) -> None:
    result = await openedx_list_content_contributors()

    assert {
        "name": "optioned",
        "description": "A contributor with options",
        "options": [{"id": "first", "label": "The first one"}, {"id": "second", "label": "The second one"}],
    } in result["response"]["contributors"]


async def test_the_chosen_option_reaches_the_builder(optioned_contributor: ContentContributor) -> None:
    with (
        patch(
            "sparkth.plugins.openedx.tools.openedx_create_basic_component",
            new=AsyncMock(return_value="block-v1:X+Y+Z+type@fake+block@b1"),
        ),
        patch("sparkth.plugins.openedx.tools.openedx_update_xblock_content", new=AsyncMock()),
    ):
        result = await openedx_add_plugin_content(add_args("optioned", "second"))

    cast(AsyncMock, optioned_contributor.builders["open-edx"]).assert_awaited_once_with("course-v1:X+Y+Z", "second")
    assert result["response"]["category"] == "fake"


async def test_an_option_for_a_contributor_without_options_is_refused_and_creates_nothing(
    fake_contributor: ContentContributor,
) -> None:
    with patch("sparkth.plugins.openedx.tools.openedx_create_basic_component", new=AsyncMock()) as create:
        result = await openedx_add_plugin_content(add_args("fake", "first"))

    create.assert_not_awaited()
    cast(AsyncMock, fake_contributor.builders["open-edx"]).assert_not_awaited()
    assert "fake" in result["error"]["message"]


async def test_a_contributor_with_options_and_none_chosen_is_refused_and_creates_nothing(
    optioned_contributor: ContentContributor,
) -> None:
    # Nothing is placed by default: the author must have chosen what to place.
    with patch("sparkth.plugins.openedx.tools.openedx_create_basic_component", new=AsyncMock()) as create:
        result = await openedx_add_plugin_content(add_args("optioned"))

    create.assert_not_awaited()
    cast(AsyncMock, optioned_contributor.builders["open-edx"]).assert_not_awaited()
    assert "option_id" in result["error"]["message"]


LOCATOR = "block-v1:X+Y+Z+type@fake+block@b1"


@pytest.fixture
def placing_contributor(owners: list[SparkthPlugin]) -> ContentContributor:
    return _register(
        owners,
        ContentContributor(
            "placing",
            "A contributor that records its placements",
            {"open-edx": AsyncMock(wraps=build_fake)},
            list_fake_options,
            AsyncMock(),
        ),
    )


async def test_the_placement_is_recorded_once_the_block_exists(placing_contributor: ContentContributor) -> None:
    with (
        patch("sparkth.plugins.openedx.tools.openedx_create_basic_component", new=AsyncMock(return_value=LOCATOR)),
        patch("sparkth.plugins.openedx.tools.openedx_update_xblock_content", new=AsyncMock()),
    ):
        await openedx_add_plugin_content(add_args("placing", "first"))

    cast(AsyncMock, placing_contributor.on_placed).assert_awaited_once_with("first")


async def test_a_failed_create_records_no_placement(placing_contributor: ContentContributor) -> None:
    failure = LMSRequestError(Method.POST, "api/contentstore/v0/xblock/course-v1:X+Y+Z", 403, "Forbidden")
    with patch("sparkth.plugins.openedx.tools.openedx_create_basic_component", new=AsyncMock(side_effect=failure)):
        await openedx_add_plugin_content(add_args("placing", "first"))

    cast(AsyncMock, placing_contributor.on_placed).assert_not_awaited()


async def test_a_failed_attribute_patch_still_records_the_placement(placing_contributor: ContentContributor) -> None:
    # The block exists, and the caller may patch its attributes again with another tool.
    failure = LMSRequestError(Method.PATCH, "api/contentstore/v0/xblock/course-v1:X+Y+Z", 500, "Boom")
    with (
        patch("sparkth.plugins.openedx.tools.openedx_create_basic_component", new=AsyncMock(return_value=LOCATOR)),
        patch("sparkth.plugins.openedx.tools.openedx_update_xblock_content", new=AsyncMock(side_effect=failure)),
    ):
        await openedx_add_plugin_content(add_args("placing", "first"))

    cast(AsyncMock, placing_contributor.on_placed).assert_awaited_once_with("first")


async def test_an_unrecorded_placement_leaves_the_block_without_attributes_and_reports_it(
    placing_contributor: ContentContributor,
) -> None:
    cast(AsyncMock, placing_contributor.on_placed).side_effect = ContentPlacementError("database unavailable")
    with (
        patch("sparkth.plugins.openedx.tools.openedx_create_basic_component", new=AsyncMock(return_value=LOCATOR)),
        patch("sparkth.plugins.openedx.tools.openedx_update_xblock_content", new=AsyncMock()) as update,
    ):
        result = await openedx_add_plugin_content(add_args("placing", "first"))

    update.assert_not_awaited()
    assert result["error"]["locator"] == LOCATOR
    assert "database unavailable" in result["error"]["message"]


async def record_off_placement(option_id: str | None) -> None:
    return None


@pytest.fixture
async def switched_off_contributor(session: AsyncSession, owners: list[SparkthPlugin]) -> ContentContributor:
    contributor = ContentContributor(
        "off",
        "A contributor whose plugin is switched off",
        {"open-edx": AsyncMock(wraps=build_fake)},
        AsyncMock(wraps=list_fake_options),
        AsyncMock(wraps=record_off_placement),
    )
    _register(owners, contributor, "off-owner")
    session.add(Plugin(name="off-owner", enabled=False))
    await session.commit()
    return contributor


async def test_a_contributor_whose_plugin_is_off_is_not_listed(
    switched_off_contributor: ContentContributor,
) -> None:
    result = await openedx_list_content_contributors()

    assert "off" not in [c["name"] for c in result["response"]["contributors"]]
    cast(AsyncMock, switched_off_contributor.list_options).assert_not_awaited()


async def test_a_contributor_whose_plugin_is_off_is_refused_and_creates_nothing(
    switched_off_contributor: ContentContributor,
) -> None:
    with patch("sparkth.plugins.openedx.tools.openedx_create_basic_component", new=AsyncMock()) as create:
        result = await openedx_add_plugin_content(add_args("off", "first"))

    assert result == {"error": {"message": "Content contributor 'off' is unavailable: its plugin is switched off"}}
    create.assert_not_awaited()
    cast(AsyncMock, switched_off_contributor.builders["open-edx"]).assert_not_awaited()
    cast(AsyncMock, switched_off_contributor.on_placed).assert_not_awaited()


@pytest.fixture
async def user_switched_off_contributor(session: AsyncSession, owners: list[SparkthPlugin]) -> ContentContributor:
    contributor = ContentContributor(
        "user-off",
        "A contributor whose plugin the user switched off",
        {"open-edx": AsyncMock(wraps=build_fake)},
        AsyncMock(wraps=list_fake_options),
        AsyncMock(wraps=record_off_placement),
    )
    _register(owners, contributor, "user-off-owner")
    plugin = Plugin(name="user-off-owner", enabled=True)
    user = User(id=1, name="U", username="u", email="u@example.com", hashed_password="x")
    session.add_all([plugin, user])
    await session.commit()
    session.add(UserPlugin(user_id=cast(int, user.id), plugin_id=cast(int, plugin.id), enabled=False))
    await session.commit()
    bind_current_user_id(1)
    return contributor


async def test_a_contributor_whose_plugin_the_user_switched_off_is_not_listed(
    user_switched_off_contributor: ContentContributor,
) -> None:
    result = await openedx_list_content_contributors()

    assert "user-off" not in [c["name"] for c in result["response"]["contributors"]]


async def test_a_contributor_whose_plugin_the_user_switched_off_is_refused_and_creates_nothing(
    user_switched_off_contributor: ContentContributor,
) -> None:
    with patch("sparkth.plugins.openedx.tools.openedx_create_basic_component", new=AsyncMock()) as create:
        result = await openedx_add_plugin_content(add_args("user-off", "first"))

    assert result == {"error": {"message": "Content contributor 'user-off' is unavailable: its plugin is switched off"}}
    create.assert_not_awaited()
    cast(AsyncMock, user_switched_off_contributor.builders["open-edx"]).assert_not_awaited()
    cast(AsyncMock, user_switched_off_contributor.on_placed).assert_not_awaited()
