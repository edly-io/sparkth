"""Revision directories and the atomic swap of a generated activity's live revision."""

import os
import time
from pathlib import Path
from unittest.mock import Mock

import pytest
from uuid6 import uuid7

from sparkth.plugins.pxc.activities import activity_dir, generated_activity_dir
from sparkth.plugins.pxc.config import get_pxc_settings
from sparkth.plugins.pxc.revisions import prune_revisions, publish_revision, remove_activity_files, revisions_dir
from sparkth.plugins.pxc.tests.conftest import question_in, staged_activity


def _rmtree_busy(path: Path) -> None:
    raise OSError("busy")


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


def jump_past_every_revision(monkeypatch: pytest.MonkeyPatch) -> None:
    """Move the clock a minute ahead, past the timestamp of every revision minted so far."""
    monkeypatch.setattr(time, "time", Mock(return_value=time.time() + 60))


def test_a_plain_directory_becomes_the_first_revision() -> None:
    activity_id = str(uuid7())
    plain = generated_activity_dir(activity_id)
    plain.mkdir(parents=True)
    (plain / "manifest.json").write_text((staged_activity("first") / "manifest.json").read_text())

    publish_revision(staged_activity("second"), activity_id)

    revisions = sorted(revisions_dir(activity_id).iterdir())
    assert [question_in(revision) for revision in revisions] == ["first", "second"]
    assert activity_dir(activity_id) == revisions[-1]


def test_pruning_keeps_a_replaced_revision_within_the_retention_window() -> None:
    activity_id = str(uuid7())
    first = publish_revision(staged_activity("first"), activity_id)
    second = publish_revision(staged_activity("second"), activity_id)

    prune_revisions(activity_id, 300)

    assert sorted(revisions_dir(activity_id).iterdir()) == [first, second]


def test_pruning_removes_a_replaced_revision_after_the_retention_window(monkeypatch: pytest.MonkeyPatch) -> None:
    activity_id = str(uuid7())
    publish_revision(staged_activity("first"), activity_id)
    publish_revision(staged_activity("second"), activity_id)
    third = publish_revision(staged_activity("third"), activity_id)
    jump_past_every_revision(monkeypatch)

    prune_revisions(activity_id, 0)

    assert list(revisions_dir(activity_id).iterdir()) == [third]


def test_pruning_never_removes_the_live_revision(monkeypatch: pytest.MonkeyPatch) -> None:
    # A slower update that started first can finish last and point the link back at an older revision.
    activity_id = str(uuid7())
    first = publish_revision(staged_activity("first"), activity_id)
    second = publish_revision(staged_activity("second"), activity_id)
    link = generated_activity_dir(activity_id)
    temporary = link.with_name(f".{activity_id}.relink")
    temporary.symlink_to(os.path.relpath(first, link.parent))
    os.replace(temporary, link)
    jump_past_every_revision(monkeypatch)

    prune_revisions(activity_id, 0)

    assert sorted(revisions_dir(activity_id).iterdir()) == [first, second]
