"""Tests for the ``"pxc"`` content contributor.

Covers what ``build_pxc_block`` produces (a ``ContentBlock`` naming the bundled activity, a
fresh placement id per call, and the sample seeded under that placement), that it is registered
on the ``LMS_CONTENT_CONTRIBUTORS`` hook, that storage failures surface as
``ContentBuildError``, and that the ``openedx`` plugin can publish it end to end.
"""

from pathlib import Path

import pytest

from sparkth.lib.content.exceptions import ContentBuildError
from sparkth.lib.content.hooks import LMS_CONTENT_CONTRIBUTORS
from sparkth.plugins.pxc.activities import state_file
from sparkth.plugins.pxc.constants import PXC_BLOCK_CATEGORY
from sparkth.plugins.pxc.contributor import build_pxc_block
from sparkth.plugins.pxc.field_store import SqliteFieldStore


@pytest.fixture(autouse=True)
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr("sparkth.plugins.pxc.activities.PXC_DATA_DIR", tmp_path)
    return tmp_path


async def test_the_block_is_a_pxc_block_naming_the_activity() -> None:
    block = await build_pxc_block("course-v1:X+Y+Z")

    assert block.category == PXC_BLOCK_CATEGORY
    assert block.settings["activity"] == "mcq"


async def test_every_placement_gets_its_own_id() -> None:
    first = await build_pxc_block("course-v1:X+Y+Z")
    second = await build_pxc_block("course-v1:X+Y+Z")

    assert first.settings["placement"] != second.settings["placement"]


async def test_the_sample_configuration_is_seeded_under_the_placement() -> None:
    block = await build_pxc_block("course-v1:X+Y+Z")
    store = SqliteFieldStore(state_file("mcq"))
    scope = ("course-v1:X+Y+Z", "mcq", block.settings["placement"], "")

    assert store.get(*scope, "question")
    assert store.get(*scope, "answers")
    assert store.get(*scope, "correct_answers") == [1]


async def test_the_contributor_is_registered_on_the_hook() -> None:
    import sparkth.plugins.pxc.plugin  # noqa: F401 — importing is what registers it

    assert LMS_CONTENT_CONTRIBUTORS.get("pxc") is not None


async def test_an_unwritable_data_dir_raises_content_build_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A file where a directory is expected makes `mkdir(parents=True)` raise `NotADirectoryError`.
    blocked = tmp_path / "not-a-dir"
    blocked.write_text("")
    monkeypatch.setattr("sparkth.plugins.pxc.activities.PXC_DATA_DIR", blocked / "nested")

    with pytest.raises(ContentBuildError):
        await build_pxc_block("course-v1:X+Y+Z")


async def test_an_unbundled_default_activity_raises_content_build_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sparkth.plugins.pxc.contributor.PXC_DEFAULT_ACTIVITY", "not-bundled")

    with pytest.raises(ContentBuildError, match="not-bundled"):
        await build_pxc_block("course-v1:X+Y+Z")


async def test_the_openedx_tool_publishes_this_contributor() -> None:
    from unittest.mock import AsyncMock, patch

    import sparkth.plugins.pxc.plugin  # noqa: F401
    from sparkth.plugins.openedx.schemas import AccessTokenPayload, AddPluginContentArgs
    from sparkth.plugins.openedx.tools import openedx_add_plugin_content

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
