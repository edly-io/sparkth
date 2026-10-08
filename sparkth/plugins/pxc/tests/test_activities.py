import json
from pathlib import Path
from uuid import UUID

import pytest
from uuid6 import uuid7

from sparkth.plugins.pxc.activities import (
    activity_dir,
    activity_names,
    generated_activity_dir,
    index_activities,
    preview_url,
    state_file,
)
from sparkth.plugins.pxc.exceptions import PxcActivityNotFound, PxcDuplicateActivityName


def _write_generated_activity(activity_id: str) -> Path:
    """Lay down the manifest a generated activity is resolved by, under ``activity_id``."""
    directory = generated_activity_dir(activity_id)
    directory.mkdir(parents=True)
    (directory / "manifest.json").write_text(json.dumps({"name": activity_id, "ui": "ui.js"}))
    return directory


def test_the_bundled_activity_is_indexed_under_its_manifest_name() -> None:
    assert "mcq" in activity_names()


def test_activity_dir_holds_the_manifest_naming_it() -> None:
    manifest = json.loads((activity_dir("mcq") / "manifest.json").read_text())

    assert manifest["name"] == "mcq"


def test_an_unknown_activity_is_rejected() -> None:
    with pytest.raises(PxcActivityNotFound, match="absent"):
        activity_dir("absent")


def test_the_state_file_is_named_after_the_activity_type(tmp_path: Path) -> None:
    assert state_file("mcq") == tmp_path / "mcq.sqlite3"


def test_state_file_rejects_a_traversal_shaped_name() -> None:
    with pytest.raises(PxcActivityNotFound, match="pwned"):
        state_file("../../../tmp/pwned")


def test_two_activities_sharing_a_name_are_rejected(tmp_path: Path) -> None:
    for directory in ("first", "second"):
        (tmp_path / directory).mkdir()
        (tmp_path / directory / "manifest.json").write_text(json.dumps({"name": "clash"}))

    with pytest.raises(PxcDuplicateActivityName, match="clash"):
        index_activities(tmp_path)


def test_a_generated_activity_lives_under_the_data_dir(tmp_path: Path) -> None:
    assert generated_activity_dir("some-id") == tmp_path / "activities" / "some-id"


def test_a_generated_activity_resolves_by_its_id() -> None:
    activity_id = str(uuid7())
    directory = _write_generated_activity(activity_id)

    assert activity_dir(activity_id) == directory


def test_an_id_with_nothing_built_under_it_is_rejected() -> None:
    with pytest.raises(PxcActivityNotFound):
        activity_dir(str(uuid7()))


def test_a_non_canonical_id_is_rejected_even_when_its_directory_exists() -> None:
    # One activity has one spelling, so its state file and storage are never split across two.
    activity_id = str(uuid7()).upper()
    _write_generated_activity(activity_id)

    with pytest.raises(PxcActivityNotFound):
        activity_dir(activity_id)


@pytest.mark.parametrize("name", ["../mcq", "/etc", "not-a-uuid"])
def test_a_path_shaped_name_is_rejected_even_when_its_directory_exists(name: str, tmp_path: Path) -> None:
    # Plant a manifest where the name would land, whenever that is inside the test's data dir.
    landing = generated_activity_dir(name).resolve()
    if landing.is_relative_to(tmp_path.resolve()):
        landing.mkdir(parents=True)
        (landing / "manifest.json").write_text(json.dumps({"name": name, "ui": "ui.js"}))

    with pytest.raises(PxcActivityNotFound):
        activity_dir(name)


def test_a_generated_activity_has_its_own_state_file(tmp_path: Path) -> None:
    activity_id = str(uuid7())
    _write_generated_activity(activity_id)

    assert state_file(activity_id) == tmp_path / f"{activity_id}.sqlite3"


def test_the_preview_url_opens_the_activities_page_on_the_activity() -> None:
    activity_id = UUID("01890a5d-ac96-774b-bcce-b302099a8057")

    assert preview_url(activity_id) == "/dashboard/pxc?activity=01890a5d-ac96-774b-bcce-b302099a8057"
