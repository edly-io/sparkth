"""Tests for the plugin's translation-catalog registration."""

from pathlib import Path

import sparkth.plugins.moodle


def test_the_plugin_locale_dir_is_registered_at_import(shipped_locale_dirs: tuple[Path, ...]) -> None:
    assert Path(sparkth.plugins.moodle.__file__).parent / "locale" in shipped_locale_dirs
