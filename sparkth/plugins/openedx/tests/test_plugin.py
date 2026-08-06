"""Tests for the open-edx plugin's declared identity and frontend metadata."""

from sparkth.lib.frontend import (
    get_plugin_display_info,
    get_plugin_sidebar_entry,
    plugin_has_frontend,
)
from sparkth.plugins.openedx.plugin import OpenEdxPlugin


def test_declares_explicit_name() -> None:
    assert OpenEdxPlugin().name == "open-edx"


def test_declares_display_info_but_no_frontend() -> None:
    plugin = OpenEdxPlugin()  # noqa: F841 - keeps the weakly-keyed hook entries alive

    display = get_plugin_display_info("open-edx")
    assert display is not None
    assert display.display_name == "Open edX"
    assert display.description

    # Backend-only plugin: no frontend page, no sidebar entry.
    assert plugin_has_frontend("open-edx") is False
    assert get_plugin_sidebar_entry("open-edx") is None
