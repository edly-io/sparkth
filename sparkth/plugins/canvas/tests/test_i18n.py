"""Tests for the plugin's translation-catalog registration."""

from pathlib import Path

import sparkth.plugins.canvas


def test_the_plugin_locale_dir_is_registered_at_import(shipped_locale_dirs: tuple[Path, ...]) -> None:
    # The suite detaches the shipped catalog dirs for the session; the
    # import-time registration is visible in the detached snapshot.
    assert Path(sparkth.plugins.canvas.__file__).parent / "locale" in shipped_locale_dirs
