"""Revision directories and the atomic swap of a generated activity's live revision."""

from pathlib import Path

import pytest
from uuid6 import uuid7

from sparkth.plugins.pxc.activities import activity_dir, generated_activity_dir
from sparkth.plugins.pxc.config import get_pxc_settings
from sparkth.plugins.pxc.exceptions import PxcActivityNotFound
from sparkth.plugins.pxc.revisions import (
    live_revision,
    publish_revision,
    remove_activity_files,
    revision_dir,
    revisions_dir,
)
from sparkth.plugins.pxc.tests.conftest import question_in, staged_activity


def _rmtree_busy(path: Path) -> None:
    raise OSError("busy")


def _replace_refused(source: Path, target: Path) -> None:
    raise OSError("link refused")


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


def test_removing_an_activity_never_published_logs_nothing(caplog: pytest.LogCaptureFixture) -> None:
    activity_id = str(uuid7())

    remove_activity_files(activity_id)

    assert not [record for record in caplog.records if record.levelname == "WARNING"]


def test_a_failed_removal_is_logged_and_not_raised(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    activity_id = str(uuid7())
    publish_revision(staged_activity("first"), activity_id)
    monkeypatch.setattr("sparkth.plugins.pxc.revisions.shutil.rmtree", _rmtree_busy)

    remove_activity_files(activity_id)

    assert any(record.levelname == "WARNING" and activity_id in record.getMessage() for record in caplog.records)


def test_a_failed_link_leaves_no_new_revision_and_keeps_the_live_one(monkeypatch: pytest.MonkeyPatch) -> None:
    activity_id = str(uuid7())
    first = publish_revision(staged_activity("first"), activity_id)
    monkeypatch.setattr("sparkth.plugins.pxc.revisions.os.replace", _replace_refused)

    with pytest.raises(OSError):
        publish_revision(staged_activity("second"), activity_id)

    assert list(revisions_dir(activity_id).iterdir()) == [first]
    assert activity_dir(activity_id) == first
    assert [entry.name for entry in generated_activity_dir(activity_id).parent.iterdir()] == [activity_id]


def test_the_live_revision_is_the_one_published_last() -> None:
    activity_id = str(uuid7())
    publish_revision(staged_activity("first"), activity_id)
    second = publish_revision(staged_activity("second"), activity_id)

    assert live_revision(activity_id) == second.name


def test_a_bundled_activity_has_no_revision() -> None:
    assert live_revision("mcq") is None


def test_a_replaced_revision_still_resolves_by_its_id() -> None:
    activity_id = str(uuid7())
    first = publish_revision(staged_activity("first"), activity_id)
    publish_revision(staged_activity("second"), activity_id)

    assert revision_dir(activity_id, first.name) == first


def test_a_revision_no_longer_on_disk_is_not_found() -> None:
    activity_id = str(uuid7())
    publish_revision(staged_activity("first"), activity_id)

    with pytest.raises(PxcActivityNotFound):
        revision_dir(activity_id, str(uuid7()))


def test_a_path_shaped_revision_is_not_found_even_where_it_lands_on_an_activity() -> None:
    activity_id = str(uuid7())
    publish_revision(staged_activity("first"), activity_id)

    with pytest.raises(PxcActivityNotFound):
        revision_dir(activity_id, f"../../activities/{activity_id}")
