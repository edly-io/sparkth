"""Tests for the moodle plugin's declared identity and frontend metadata."""

from sparkth.lib.frontend import (
    get_plugin_display_info,
    get_plugin_sidebar_entry,
    plugin_has_frontend,
)
from sparkth.lib.mcp.hooks import MCP_TOOLS
from sparkth.plugins.moodle.plugin import MoodlePlugin
from sparkth.plugins.moodle.tools import moodle_about


def test_declares_explicit_name() -> None:
    assert MoodlePlugin().name == "moodle"


def test_declares_display_info_but_no_frontend() -> None:
    plugin = MoodlePlugin()  # noqa: F841 - keeps the weakly-keyed hook entries alive

    display = get_plugin_display_info("moodle")
    assert display is not None
    assert display.display_name == "Moodle"
    assert display.description

    assert plugin_has_frontend("moodle") is False
    assert get_plugin_sidebar_entry("moodle") is None


async def test_registers_about_tool() -> None:
    plugin = MoodlePlugin()
    names = {tool.name for owner, tool in MCP_TOOLS.iter_items() if owner is plugin}
    assert "moodle_about" in names

    about = (await moodle_about())["about"]
    assert "publish" in about.lower()
