"""Revision directories and the atomic swap of a generated activity's live revision."""

import os
import shutil
import time
from pathlib import Path
from unittest.mock import Mock
from uuid import UUID

import pytest
from uuid6 import uuid7

from sparkth.plugins.pxc.activities import activity_dir, generated_activity_dir, state_file
from sparkth.plugins.pxc.config import get_pxc_settings
from sparkth.plugins.pxc.exceptions import PxcActivityNotFound
from sparkth.plugins.pxc.revisions import (
    live_revision,
    prune_revisions,
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
    activity_id = uuid7()
    publish_revision(staged_activity("first"), str(activity_id))

    remove_activity_files(activity_id)

    assert not generated_activity_dir(str(activity_id)).is_symlink()
    assert not revisions_dir(str(activity_id)).exists()


def write_state_and_storage(activity_id: UUID) -> list[Path]:
    """Publish an activity and write its state file, sidecars and a learner file; return those paths."""
    publish_revision(staged_activity("first"), str(activity_id))
    state = state_file(str(activity_id))
    stored = get_pxc_settings().data_dir / "storage" / str(activity_id) / "answer.txt"
    stored.parent.mkdir(parents=True)
    paths = [state, state.with_name(state.name + "-wal"), state.with_name(state.name + "-shm"), stored]
    for path in paths:
        path.write_text("x")
    return paths


def test_removing_an_activity_removes_its_state_and_storage() -> None:
    removed, kept = uuid7(), uuid7()
    removed_paths = write_state_and_storage(removed)
    kept_paths = write_state_and_storage(kept)

    remove_activity_files(removed)

    assert not any(path.exists() for path in removed_paths)
    assert all(path.exists() for path in kept_paths)


def test_removing_a_plain_directory_activity_removes_the_directory(caplog: pytest.LogCaptureFixture) -> None:
    activity_id = uuid7()
    directory = generated_activity_dir(str(activity_id))
    directory.mkdir(parents=True)
    (directory / "manifest.json").write_text("{}")

    remove_activity_files(activity_id)

    assert not directory.exists()
    assert not [record for record in caplog.records if record.levelname == "WARNING"]


def test_removing_an_activity_whose_link_is_gone_still_removes_its_state() -> None:
    activity_id = uuid7()
    paths = write_state_and_storage(activity_id)
    generated_activity_dir(str(activity_id)).unlink()

    remove_activity_files(activity_id)

    assert not any(path.exists() for path in paths)


def test_removing_an_activity_never_published_logs_nothing(caplog: pytest.LogCaptureFixture) -> None:
    activity_id = uuid7()

    remove_activity_files(activity_id)

    assert not [record for record in caplog.records if record.levelname == "WARNING"]


def test_a_failed_removal_is_logged_and_not_raised(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    activity_id = uuid7()
    publish_revision(staged_activity("first"), str(activity_id))
    monkeypatch.setattr("sparkth.plugins.pxc.revisions.shutil.rmtree", _rmtree_busy)

    remove_activity_files(activity_id)

    assert any(record.levelname == "WARNING" and str(activity_id) in record.getMessage() for record in caplog.records)


_real_rmtree = shutil.rmtree


def _rmtree_unless_revisions(path: Path) -> None:
    if path.parent.name == "revisions":
        raise OSError("busy")
    _real_rmtree(path)


def test_one_failed_removal_does_not_stop_the_others(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    activity_id = uuid7()
    paths = write_state_and_storage(activity_id)
    monkeypatch.setattr("sparkth.plugins.pxc.revisions.shutil.rmtree", _rmtree_unless_revisions)

    remove_activity_files(activity_id)

    assert not any(path.exists() for path in paths)
    assert revisions_dir(str(activity_id)).exists()
    assert any(r.levelname == "WARNING" and str(activity_id) in r.getMessage() for r in caplog.records)


def jump_past_every_revision(monkeypatch: pytest.MonkeyPatch) -> None:
    """Move the clock a minute ahead, past the timestamp of every revision minted so far."""
    monkeypatch.setattr(time, "time", Mock(return_value=time.time() + 60))


def age_revision(revision: Path, seconds: int) -> Path:
    """Rename a revision so its uuid7 says it went live ``seconds`` ago, and return its new path."""
    went_live_ms = int((time.time() - seconds) * 1000)
    return revision.rename(revision.with_name(str(UUID(int=went_live_ms << 80, version=7))))


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


def test_pruning_keeps_a_revision_whose_successor_went_live_within_the_window() -> None:
    # The first revision is two hours old, but the one that replaced it just went live.
    activity_id = str(uuid7())
    first = publish_revision(staged_activity("first"), activity_id)
    second = publish_revision(staged_activity("second"), activity_id)
    aged_first = age_revision(first, 7200)

    prune_revisions(activity_id, 3600)

    assert sorted(revisions_dir(activity_id).iterdir()) == [aged_first, second]


def test_pruning_removes_only_the_revisions_whose_successor_outlived_the_window() -> None:
    activity_id = str(uuid7())
    oldest = publish_revision(staged_activity("oldest"), activity_id)
    middle = publish_revision(staged_activity("middle"), activity_id)
    newest = publish_revision(staged_activity("newest"), activity_id)
    age_revision(oldest, 10800)
    aged_middle = age_revision(middle, 7200)

    prune_revisions(activity_id, 3600)

    assert sorted(revisions_dir(activity_id).iterdir()) == [aged_middle, newest]


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


def test_pruning_skips_an_entry_that_is_not_a_revision(monkeypatch: pytest.MonkeyPatch) -> None:
    # A copy named after the revision it backs up sorts right after it.
    activity_id = str(uuid7())
    first = publish_revision(staged_activity("first"), activity_id)
    publish_revision(staged_activity("second"), activity_id)
    third = publish_revision(staged_activity("third"), activity_id)
    backup = first.with_name(f"{first.name}.bak")
    shutil.copytree(first, backup)
    jump_past_every_revision(monkeypatch)

    prune_revisions(activity_id, 0)

    assert sorted(revisions_dir(activity_id).iterdir()) == [backup, third]
