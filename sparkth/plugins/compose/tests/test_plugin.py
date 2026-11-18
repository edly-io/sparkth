"""Tests for the compose plugin's declared identity, settings and frontend metadata."""

import pytest
from pydantic import ValidationError

from sparkth.lib.frontend import (
    get_plugin_display_info,
    get_plugin_sidebar_entry,
    plugin_has_frontend,
)
from sparkth.plugins.compose.config import get_compose_settings
from sparkth.plugins.compose.plugin import ComposePlugin


def test_plugin_is_named_compose() -> None:
    assert ComposePlugin().name == "compose"


def test_a_setting_compose_cannot_read_stops_the_plugin_loading(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMPOSE_PLANNER_MODEL", "largest")
    get_compose_settings.cache_clear()

    with pytest.raises(ValidationError, match="planner_model"):
        ComposePlugin()


def test_declares_frontend_metadata() -> None:
    plugin = ComposePlugin()  # noqa: F841 - keeps the weakly-keyed hook entries alive

    display = get_plugin_display_info("compose")
    assert display is not None
    assert display.display_name == "Compose"
    assert display.description == "Transform your resources into courses with AI"

    sidebar = get_plugin_sidebar_entry("compose")
    assert sidebar is not None
    assert sidebar.label == "Compose"
    assert sidebar.order == 1

    assert plugin_has_frontend("compose") is True
