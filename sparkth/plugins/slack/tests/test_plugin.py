"""Tests for the slack plugin's declared identity and frontend metadata."""

from sparkth.lib.frontend import (
    get_plugin_display_info,
    get_plugin_sidebar_entry,
    plugin_has_frontend,
)
from sparkth.plugins.slack.plugin import Slack


def test_declares_explicit_name() -> None:
    assert Slack().name == "slack"


def test_declares_frontend_metadata() -> None:
    plugin = Slack()  # noqa: F841 - keeps the weakly-keyed hook entries alive

    display = get_plugin_display_info("slack")
    assert display is not None
    assert display.display_name == "Slack TA Bot"
    assert display.description == "Answer student questions in Slack from your course materials"

    sidebar = get_plugin_sidebar_entry("slack")
    assert sidebar is not None
    assert sidebar.label == "Slack TA Bot"
    assert sidebar.order == 3

    assert plugin_has_frontend("slack") is True
