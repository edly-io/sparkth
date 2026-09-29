"""Tests for the canvas plugin's declared identity and frontend metadata."""

from sparkth.lib.frontend import (
    get_plugin_display_info,
    get_plugin_sidebar_entry,
    plugin_has_frontend,
)
from sparkth.lib.mcp.hooks import MCP_TOOLS
from sparkth.plugins.canvas.plugin import CanvasPlugin
from sparkth.plugins.canvas.tools import canvas_about


def test_declares_explicit_name() -> None:
    assert CanvasPlugin().name == "canvas"


def test_declares_display_info_but_no_frontend() -> None:
    plugin = CanvasPlugin()  # noqa: F841 - keeps the weakly-keyed hook entries alive

    display = get_plugin_display_info("canvas")
    assert display is not None
    assert display.display_name == "Canvas"
    assert display.description

    # Backend-only plugin: no frontend page, no sidebar entry.
    assert plugin_has_frontend("canvas") is False
    assert get_plugin_sidebar_entry("canvas") is None


async def test_registers_about_tool() -> None:
    plugin = CanvasPlugin()
    names = {tool.name for owner, tool in MCP_TOOLS.iter_items() if owner is plugin}
    assert "canvas_about" in names

    about = (await canvas_about())["about"]
    assert "publish" in about.lower()
