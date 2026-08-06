"""Tests for the chat plugin's declared identity and frontend metadata."""

from sparkth.lib.frontend import (
    get_plugin_display_info,
    get_plugin_sidebar_entry,
    plugin_has_frontend,
)
from sparkth.plugins.chat.plugin import ChatPlugin


def test_declares_explicit_name() -> None:
    assert ChatPlugin().name == "chat"


def test_declares_frontend_metadata() -> None:
    plugin = ChatPlugin()  # noqa: F841 - keeps the weakly-keyed hook entries alive

    display = get_plugin_display_info("chat")
    assert display is not None
    assert display.display_name == "Create Course"
    assert display.description == "Transform your resources into courses with AI"

    sidebar = get_plugin_sidebar_entry("chat")
    assert sidebar is not None
    assert sidebar.label == "Create Course"
    assert sidebar.order == 1

    assert plugin_has_frontend("chat") is True
