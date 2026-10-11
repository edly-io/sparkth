"""Revision directories and the atomic swap of a generated activity's live revision."""

from pathlib import Path

import pytest
from uuid6 import uuid7

from sparkth.plugins.pxc.activities import activity_dir, generated_activity_dir
from sparkth.plugins.pxc.config import get_pxc_settings
from sparkth.plugins.pxc.revisions import publish_revision, remove_activity_files, revisions_dir
from sparkth.plugins.pxc.tests.conftest import question_in, staged_activity


def test_a_published_activity_resolves_to_its_revision() -> None:
    activity_id = str(uuid7())

    revision = publish_revision(staged_activity("first"), activity_id)

    assert activity_dir(activity_id) == revision
    assert revision.parent == revisions_dir(activity_id)
    assert question_in(activity_dir(activity_id)) == "first"


def test_publishing_again_makes_the_new_revision_live() -> None:
    activity_id = str(uuid7())
    publish_revision(staged_activity("first"), activity_id)

    publish_revision(staged_activity("second"), activity_id)

    assert question_in(activity_dir(activity_id)) == "second"


def test_publishing_again_keeps_the_replaced_revisions_files() -> None:
    # A runtime that resolved the old revision before the swap keeps reading a complete activity.
    activity_id = str(uuid7())
    first = publish_revision(staged_activity("first"), activity_id)
    pinned = activity_dir(activity_id)

    publish_revision(staged_activity("second"), activity_id)

    assert pinned == first
    assert question_in(pinned) == "first"


def test_an_activity_still_resolves_after_its_data_dir_moves(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PXC_DATA_DIR", str(tmp_path / "first"))
    get_pxc_settings.cache_clear()
    activity_id = str(uuid7())
    publish_revision(staged_activity("first"), activity_id)
    (tmp_path / "first").rename(tmp_path / "moved")
    monkeypatch.setenv("PXC_DATA_DIR", str(tmp_path / "moved"))
    get_pxc_settings.cache_clear()

    assert question_in(activity_dir(activity_id)) == "first"


def test_removing_an_activity_leaves_no_link_and_no_revision() -> None:
    activity_id = str(uuid7())
    publish_revision(staged_activity("first"), activity_id)

    remove_activity_files(activity_id)

    assert not generated_activity_dir(activity_id).is_symlink()
    assert not revisions_dir(activity_id).exists()
