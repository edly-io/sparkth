"""Tests for the ``"pxc"`` content contributor.

Covers what ``build_pxc_block`` produces (a ``ContentBlock`` naming the chosen activity and a
fresh activity instance id per call), that it writes no activity state, that an activity instance it mints launches with
the activity's own configuration, and that constructing the plugin registers it on the
``LMS_CONTENT_CONTRIBUTORS`` hook.
"""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from pxc.lib.permission import Permission
from sqlalchemy.exc import OperationalError
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.content.exceptions import ContentBuildError, ContentPlacementError
from sparkth.lib.content.hooks import LMS_CONTENT_CONTRIBUTORS, ContentOption
from sparkth.lib.exceptions.auth import NoAuthenticatedUser
from sparkth.lib.models import User
from sparkth.plugins.pxc.activities import generated_activity_dir
from sparkth.plugins.pxc.config import get_pxc_settings
from sparkth.plugins.pxc.constants import PXC_BLOCK_CATEGORY
from sparkth.plugins.pxc.contributor import build_pxc_block, list_pxc_options
from sparkth.plugins.pxc.models import PxcActivity
from sparkth.plugins.pxc.plugin import PxcPlugin
from sparkth.plugins.pxc.runtime import build_runtime, read_state
from sparkth.plugins.pxc.store import insert_activity
from sparkth.plugins.pxc.tests.conftest import act_as
from sparkth.plugins.pxc.tokens import LaunchClaims


async def test_the_block_is_a_pxc_block_naming_the_activity() -> None:
    block = await build_pxc_block("course-1", "mcq")

    assert block.kind == PXC_BLOCK_CATEGORY
    assert block.attributes["activity"] == "mcq"


async def test_every_activity_instance_gets_its_own_id() -> None:
    first = await build_pxc_block("course-1", "mcq")
    second = await build_pxc_block("course-1", "mcq")

    assert first.attributes["activity_instance"] != second.attributes["activity_instance"]


async def test_building_a_block_writes_nothing(tmp_path: Path) -> None:
    # The decoupling this contributor rests on: it names an activity and mints an id for it, and
    # knows nothing else about it. Writing a configuration would mean knowing which fields that
    # activity declares, which is true of exactly one of them. The absent state file is the
    # evidence, since nothing about the returned block would differ either way.
    await build_pxc_block("course-1", "mcq")

    # `pxc_settings` points PXC_DATA_DIR at this same tmp_path.
    assert list(tmp_path.iterdir()) == []


@pytest.mark.wasm
async def test_a_minted_activity_instance_launches_with_the_activitys_own_configuration() -> None:
    # What the seeding was for: a learner opening a freshly placed activity sees a question
    # rather than a blank. The activity declares it as its fields' defaults, and the runtime
    # serves those for any activity instance nobody has configured yet.
    block = await build_pxc_block("course-1", "mcq")
    claims = LaunchClaims("mcq", block.attributes["activity_instance"], "course-1", "learner-7", Permission.play)

    state = read_state(build_runtime(claims))

    assert state["question"] == "What is 2 + 2?"
    assert state["answers"] == ["3", "4", "5"]


async def test_constructing_the_plugin_registers_the_contributor() -> None:
    plugin = PxcPlugin()

    assert [c.name for owner, c in LMS_CONTENT_CONTRIBUTORS.iter_items() if owner is plugin] == ["pxc"]


async def test_constructing_the_plugin_again_registers_the_same_contributor() -> None:
    # The loader constructs the plugin and these tests construct their own instances, so every
    # construction registers the same contributor again rather than colliding with itself.
    first = PxcPlugin()
    second = PxcPlugin()

    owned = [c for owner, c in LMS_CONTENT_CONTRIBUTORS.iter_items() if owner is first or owner is second]
    assert len(owned) == 2
    assert owned[0] == owned[1]


async def test_no_chosen_activity_places_nothing() -> None:
    with pytest.raises(ContentBuildError, match="Choose"):
        await build_pxc_block("course-1", None)


def nobody() -> int:
    raise NoAuthenticatedUser("No authenticated user is bound")


async def test_options_are_the_bundled_activities_then_the_authors_own(
    authored_activity: PxcActivity, authors: tuple[User, User]
) -> None:
    act_as(authors[0])

    options = await list_pxc_options()

    built_at = f"{authored_activity.created_at:%Y-%m-%d %H:%M} UTC"
    assert options == [
        ContentOption("mcq", "mcq"),
        ContentOption(str(authored_activity.id), f"Capital cities ({built_at})"),
    ]


async def test_activities_sharing_a_title_get_distinct_labels(
    session: AsyncSession, authors: tuple[User, User]
) -> None:
    # An edit builds a new activity under the same title, so the build time tells them apart.
    owner = authors[0]
    assert owner.id is not None
    for hour in (9, 10):
        created_at = datetime(2026, 10, 8, hour, 30, tzinfo=UTC)
        await insert_activity(
            session, PxcActivity(owner_user_id=owner.id, title="Fractions", description="", created_at=created_at)
        )
    act_as(owner)

    options = await list_pxc_options()

    assert [option.label for option in options] == [
        "mcq",
        "Fractions (2026-10-08 10:30 UTC)",
        "Fractions (2026-10-08 09:30 UTC)",
    ]


async def test_options_offer_only_the_authors_newest_activities(
    session: AsyncSession, authors: tuple[User, User], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Every option reaches the model, so a prolific author's list is capped at the newest.
    monkeypatch.setenv("PXC_LIST_ACTIVITIES_LIMIT", "2")
    get_pxc_settings.cache_clear()
    owner = authors[0]
    assert owner.id is not None
    for day in (1, 2, 3):
        created_at = datetime(2026, 10, day, tzinfo=UTC)
        await insert_activity(
            session, PxcActivity(owner_user_id=owner.id, title=f"Day {day}", description="", created_at=created_at)
        )
    act_as(owner)

    options = await list_pxc_options()

    assert [option.label for option in options] == [
        "mcq",
        "Day 3 (2026-10-03 00:00 UTC)",
        "Day 2 (2026-10-02 00:00 UTC)",
    ]


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


async def test_a_placed_block_is_titled_after_its_activity(
    authored_activity: PxcActivity, authors: tuple[User, User]
) -> None:
    act_as(authors[0])

    generated = await build_pxc_block("course-v1:X+Y+Z", str(authored_activity.id))
    bundled = await build_pxc_block("course-v1:X+Y+Z", "mcq")

    assert generated.title == "Capital cities"
    assert bundled.title == "mcq"


async def test_another_author_cannot_place_someone_elses_activity(
    authored_activity: PxcActivity, authors: tuple[User, User]
) -> None:
    act_as(authors[1])

    with pytest.raises(ContentBuildError):
        await build_pxc_block("course-1", str(authored_activity.id))


async def test_an_owned_activity_whose_files_are_gone_cannot_be_placed(
    authored_activity: PxcActivity, authors: tuple[User, User]
) -> None:
    act_as(authors[0])
    (generated_activity_dir(str(authored_activity.id)) / "manifest.json").unlink()

    with pytest.raises(ContentBuildError):
        await build_pxc_block("course-v1:X+Y+Z", str(authored_activity.id))


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


async def record_registered_placement(option_id: str) -> None:
    """Record a placement through the contributor the plugin registered, as a publishing tool does."""
    contributor = next(c for _owner, c in LMS_CONTENT_CONTRIBUTORS.iter_items() if c.name == "pxc")
    assert contributor.callback is not None
    await contributor.callback(option_id)


async def test_building_a_block_records_no_placement(
    session: AsyncSession, authored_activity: PxcActivity, authors: tuple[User, User]
) -> None:
    # The LMS may still refuse to create the block, so the activity is not in any course yet.
    act_as(authors[0])

    await build_pxc_block("course-1", str(authored_activity.id))

    await session.refresh(authored_activity)
    assert authored_activity.placed_at is None


async def test_a_created_block_records_that_its_activity_was_placed(
    session: AsyncSession, authored_activity: PxcActivity
) -> None:
    await record_registered_placement(str(authored_activity.id))

    await session.refresh(authored_activity)
    assert authored_activity.placed_at is not None


async def test_placing_an_activity_again_keeps_its_first_placement_time(
    session: AsyncSession, authored_activity: PxcActivity
) -> None:
    await record_registered_placement(str(authored_activity.id))
    await session.refresh(authored_activity)
    first = authored_activity.placed_at

    await record_registered_placement(str(authored_activity.id))

    await session.refresh(authored_activity)
    assert authored_activity.placed_at == first


async def test_placing_a_bundled_activity_marks_no_generated_activity(
    session: AsyncSession, authored_activity: PxcActivity
) -> None:
    await record_registered_placement("mcq")

    await session.refresh(authored_activity)
    assert authored_activity.placed_at is None


async def test_a_placement_the_database_cannot_record_is_reported(
    monkeypatch: pytest.MonkeyPatch, authored_activity: PxcActivity
) -> None:
    failure = OperationalError("UPDATE pxc_activities", {}, Exception("database unavailable"))
    monkeypatch.setattr("sparkth.plugins.pxc.contributor.mark_placed", AsyncMock(side_effect=failure))

    with pytest.raises(ContentPlacementError):
        await record_registered_placement(str(authored_activity.id))
