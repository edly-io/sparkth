"""Reading a plugin's text assets."""

from pathlib import Path

import pytest

from sparkth.lib.assets import read_asset


def test_it_reads_the_asset_beside_the_module_without_surrounding_whitespace(tmp_path: Path) -> None:
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "prompt.txt").write_text("\n  Answer briefly.\n\n", encoding="utf-8")

    assert read_asset(str(tmp_path / "constants.py"), "prompt.txt") == "Answer briefly."


def test_a_missing_asset_is_not_swallowed(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_asset(str(tmp_path / "constants.py"), "missing.txt")
