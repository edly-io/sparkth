"""Tests for the google-drive plugin's declared identity and frontend metadata."""

from sparkth.lib.frontend import (
    get_plugin_display_info,
    get_plugin_sidebar_entry,
    plugin_has_frontend,
)
from sparkth.plugins.googledrive.plugin import GoogleDrivePlugin


def test_declares_explicit_name() -> None:
    assert GoogleDrivePlugin().name == "google-drive"


def test_declares_frontend_metadata_without_sidebar_entry() -> None:
    plugin = GoogleDrivePlugin()  # noqa: F841 - keeps the weakly-keyed hook entries alive

    display = get_plugin_display_info("google-drive")
    assert display is not None
    assert display.display_name == "Google Drive"
    assert display.description == "All imported files from your connected plugins"

    # Has a frontend page but no sidebar entry (mirrors the frontend definition).
    assert plugin_has_frontend("google-drive") is True
    assert get_plugin_sidebar_entry("google-drive") is None
