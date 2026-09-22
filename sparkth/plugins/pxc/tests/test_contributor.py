"""Tests for the ``"pxc"`` content contributor.

Covers what ``build_pxc_block`` produces (a ``ContentBlock`` naming the bundled activity and a
fresh placement id per call), that it writes nothing, that a placement it mints launches with
the activity's own configuration, that constructing the plugin registers it on the
``LMS_CONTENT_CONTRIBUTORS`` hook, and that the ``openedx`` plugin can publish it end to end.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from sparkth.lib.content.exceptions import ContentBuildError
from sparkth.lib.content.hooks import LMS_CONTENT_CONTRIBUTORS
from sparkth.plugins.pxc.constants import PXC_BLOCK_CATEGORY
from sparkth.plugins.pxc.contributor import build_pxc_block
from sparkth.plugins.pxc.plugin import PxcPlugin
from sparkth.plugins.pxc.runtime import build_runtime, read_state
from sparkth.plugins.pxc.tokens import LaunchClaims


@pytest.fixture(autouse=True)
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr("sparkth.plugins.pxc.activities.PXC_DATA_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def unregistered() -> Iterator[None]:
    # Importing this module already registered the contributor, so a test asserting that
    # *construction* registers it has to start from an empty hook. The hook is process-global,
    # hence the restore.
    LMS_CONTENT_CONTRIBUTORS.remove("pxc")
    yield
    PxcPlugin()


async def test_the_block_is_a_pxc_block_naming_the_activity() -> None:
    block = await build_pxc_block("course-v1:X+Y+Z")

    assert block.kind == PXC_BLOCK_CATEGORY
    assert block.attributes["activity"] == "mcq"


async def test_every_placement_gets_its_own_id() -> None:
    first = await build_pxc_block("course-v1:X+Y+Z")
    second = await build_pxc_block("course-v1:X+Y+Z")

    assert first.attributes["placement"] != second.attributes["placement"]


async def test_building_a_block_writes_nothing(data_dir: Path) -> None:
    # The decoupling this contributor rests on: it names an activity and mints an id for it, and
    # knows nothing else about it. Writing a configuration would mean knowing which fields that
    # activity declares, which is true of exactly one of them. The absent state file is the
    # evidence, since nothing about the returned block would differ either way.
    await build_pxc_block("course-v1:X+Y+Z")

    assert list(data_dir.iterdir()) == []


@pytest.mark.wasm
async def test_a_minted_placement_launches_with_the_activitys_own_configuration() -> None:
    # What the seeding was for: a learner opening a freshly placed activity sees a question
    # rather than a blank. The activity declares it as its fields' defaults, and the runtime
    # serves those for any placement nobody has configured yet.
    block = await build_pxc_block("course-v1:X+Y+Z")
    claims = LaunchClaims("mcq", block.attributes["placement"], "course-v1:X+Y+Z", "learner-7")

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
    monkeypatch.setattr("sparkth.plugins.pxc.contributor.PXC_DEFAULT_ACTIVITY", "not-bundled")

    with pytest.raises(ContentBuildError, match="not-bundled"):
        await build_pxc_block("course-v1:X+Y+Z")


async def test_the_openedx_tool_publishes_this_contributor() -> None:
    from unittest.mock import AsyncMock, patch

    from sparkth.plugins.openedx.schemas import AccessTokenPayload, AddPluginContentArgs
    from sparkth.plugins.openedx.tools import openedx_add_plugin_content

    PxcPlugin()  # constructing the plugin is what puts the contributor on the hook
    auth = AccessTokenPayload(access_token="t", lms_url="https://lms", studio_url="https://studio")
    with (
        patch(
            "sparkth.plugins.openedx.tools.openedx_create_basic_component",
            new=AsyncMock(return_value="block-v1:X+Y+Z+type@pxc+block@b1"),
        ),
        patch("sparkth.plugins.openedx.tools.openedx_update_xblock_content", new=AsyncMock()) as update,
    ):
        result = await openedx_add_plugin_content(
            AddPluginContentArgs(
                auth=auth,
                course_id="course-v1:X+Y+Z",
                unit_locator="block-v1:X+Y+Z+type@vertical+block@u1",
                contributor="pxc",
            )
        )

    assert result["response"]["category"] == "pxc"
    assert update.await_args is not None
    assert update.await_args.args[4]["activity"] == "mcq"
