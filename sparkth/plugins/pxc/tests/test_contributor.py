"""Tests for the ``"pxc"`` content contributor.

Covers what ``build_pxc_block`` produces (a ``ContentBlock`` naming the bundled activity and a
fresh activity instance id per call), that it writes nothing, that an activity instance it mints launches with
the activity's own configuration, and that constructing the plugin registers it on the
``LMS_CONTENT_CONTRIBUTORS`` hook.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from pxc.lib.permission import Permission

from sparkth.core.models.user import User
from sparkth.lib.content.exceptions import ContentBuildError
from sparkth.lib.content.hooks import LMS_CONTENT_CONTRIBUTORS, ContentOption
from sparkth.lib.exceptions.auth import NoAuthenticatedUser
from sparkth.plugins.pxc.config import get_pxc_settings
from sparkth.plugins.pxc.constants import PXC_BLOCK_CATEGORY
from sparkth.plugins.pxc.contributor import build_pxc_block, list_pxc_options
from sparkth.plugins.pxc.models import PxcActivity
from sparkth.plugins.pxc.plugin import PxcPlugin
from sparkth.plugins.pxc.runtime import build_runtime, read_state
from sparkth.plugins.pxc.tests.conftest import act_as
from sparkth.plugins.pxc.tokens import LaunchClaims


@pytest.fixture
def unregistered() -> Iterator[None]:
    # Importing this module already registered the contributor, so a test asserting that
    # *construction* registers it has to start from an empty hook. The hook is process-global,
    # hence the restore.
    LMS_CONTENT_CONTRIBUTORS.remove("pxc")
    yield
    PxcPlugin()


async def test_the_block_is_a_pxc_block_naming_the_activity() -> None:
    block = await build_pxc_block("course-1", None)

    assert block.kind == PXC_BLOCK_CATEGORY
    assert block.attributes["activity"] == "mcq"


async def test_every_activity_instance_gets_its_own_id() -> None:
    first = await build_pxc_block("course-1", None)
    second = await build_pxc_block("course-1", None)

    assert first.attributes["activity_instance"] != second.attributes["activity_instance"]


async def test_building_a_block_writes_nothing(tmp_path: Path) -> None:
    # The decoupling this contributor rests on: it names an activity and mints an id for it, and
    # knows nothing else about it. Writing a configuration would mean knowing which fields that
    # activity declares, which is true of exactly one of them. The absent state file is the
    # evidence, since nothing about the returned block would differ either way.
    await build_pxc_block("course-1", None)

    # `pxc_settings` points PXC_DATA_DIR at this same tmp_path.
    assert list(tmp_path.iterdir()) == []


@pytest.mark.wasm
async def test_a_minted_activity_instance_launches_with_the_activitys_own_configuration() -> None:
    # What the seeding was for: a learner opening a freshly placed activity sees a question
    # rather than a blank. The activity declares it as its fields' defaults, and the runtime
    # serves those for any activity instance nobody has configured yet.
    block = await build_pxc_block("course-1", None)
    claims = LaunchClaims("mcq", block.attributes["activity_instance"], "course-1", "learner-7", Permission.play)

    state = read_state(build_runtime(claims))

    assert state["question"] == "What is 2 + 2?"
    assert state["answers"] == ["3", "4", "5"]


async def test_constructing_the_plugin_registers_the_contributor(unregistered: None) -> None:
    PxcPlugin()

    assert LMS_CONTENT_CONTRIBUTORS.get("pxc") is not None


async def test_constructing_the_plugin_again_keeps_one_registration(unregistered: None) -> None:
    # The loader constructs the plugin and these tests construct their own instances, so every
    # construction re-registers the same contributor rather than colliding with itself.
    PxcPlugin()
    registered = LMS_CONTENT_CONTRIBUTORS.get("pxc")

    PxcPlugin()

    assert registered is not None
    assert LMS_CONTENT_CONTRIBUTORS.get("pxc") is registered


async def test_an_unbundled_default_activity_raises_content_build_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PXC_DEFAULT_ACTIVITY", "not-bundled")
    get_pxc_settings.cache_clear()

    with pytest.raises(ContentBuildError, match="not-bundled"):
        await build_pxc_block("course-1", None)


def nobody() -> int:
    raise NoAuthenticatedUser("No authenticated user is bound")


async def test_options_are_the_bundled_activities_then_the_authors_own(
    authored_activity: PxcActivity, authors: tuple[User, User]
) -> None:
    act_as(authors[0])

    options = await list_pxc_options()

    assert options == [ContentOption("mcq", "mcq"), ContentOption(str(authored_activity.id), "Capital cities")]


async def test_options_leave_out_another_authors_activities(
    authored_activity: PxcActivity, authors: tuple[User, User]
) -> None:
    act_as(authors[1])

    assert await list_pxc_options() == [ContentOption("mcq", "mcq")]


async def test_options_with_nobody_authenticated_are_the_bundled_activities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sparkth.plugins.pxc.contributor.current_user_id", nobody)

    assert await list_pxc_options() == [ContentOption("mcq", "mcq")]


async def test_a_bundled_activity_can_be_placed_by_anyone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sparkth.plugins.pxc.contributor.current_user_id", nobody)

    block = await build_pxc_block("course-1", "mcq")

    assert block.attributes["activity"] == "mcq"


async def test_the_owner_places_their_own_activity(authored_activity: PxcActivity, authors: tuple[User, User]) -> None:
    act_as(authors[0])

    block = await build_pxc_block("course-1", str(authored_activity.id))

    assert block.attributes["activity"] == str(authored_activity.id)


async def test_another_author_cannot_place_someone_elses_activity(
    authored_activity: PxcActivity, authors: tuple[User, User]
) -> None:
    act_as(authors[1])

    with pytest.raises(ContentBuildError):
        await build_pxc_block("course-1", str(authored_activity.id))


async def test_a_generated_activity_cannot_be_placed_with_nobody_authenticated(
    monkeypatch: pytest.MonkeyPatch, authored_activity: PxcActivity
) -> None:
    monkeypatch.setattr("sparkth.plugins.pxc.contributor.current_user_id", nobody)

    with pytest.raises(ContentBuildError):
        await build_pxc_block("course-1", str(authored_activity.id))


async def test_an_option_that_is_neither_bundled_nor_a_uuid_is_refused(authors: tuple[User, User]) -> None:
    act_as(authors[0])

    with pytest.raises(ContentBuildError):
        await build_pxc_block("course-1", "../../etc")
