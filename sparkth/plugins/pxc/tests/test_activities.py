import json
from pathlib import Path

import pytest

from sparkth.plugins.pxc.activities import activity_dir, activity_names, index_activities, state_file
from sparkth.plugins.pxc.exceptions import PxcActivityNotFound, PxcDuplicateActivityName


def test_the_bundled_activity_is_indexed_under_its_manifest_name() -> None:
    assert "mcq" in activity_names()


def test_activity_dir_holds_the_manifest_naming_it() -> None:
    manifest = json.loads((activity_dir("mcq") / "manifest.json").read_text())

    assert manifest["name"] == "mcq"


def test_an_unknown_activity_is_rejected() -> None:
    with pytest.raises(PxcActivityNotFound, match="absent"):
        activity_dir("absent")


def test_the_state_file_is_named_after_the_activity_type(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sparkth.plugins.pxc.activities.PXC_DATA_DIR", tmp_path)

    assert state_file("mcq") == tmp_path / "mcq.sqlite3"


def test_two_activities_sharing_a_name_are_rejected(tmp_path: Path) -> None:
    for directory in ("first", "second"):
        (tmp_path / directory).mkdir()
        (tmp_path / directory / "manifest.json").write_text(json.dumps({"name": "clash"}))

    with pytest.raises(PxcDuplicateActivityName, match="clash"):
        index_activities(tmp_path)
