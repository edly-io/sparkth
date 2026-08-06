"""Tests for the frontend-facing plugin declaration hooks (``sparkth.lib.frontend``).

A plugin declares what the frontend should show for it through three per-concern
hooks (display info, a sidebar entry, and a frontend-app marker) instead of one
monolithic manifest object. Human-facing names are passed positionally.
"""

from sparkth.lib.frontend import (
    get_plugin_display_info,
    get_plugin_sidebar_entry,
    plugin_has_frontend,
)
from sparkth.lib.frontend.hooks import (
    DISPLAY_INFO,
    FRONTEND_APPS,
    SIDEBAR_ENTRIES,
    DisplayInfo,
    FrontendApp,
    SidebarEntry,
)
from sparkth.lib.plugins import SparkthPlugin


class TestDisplayInfo:
    def test_display_name_and_description_are_positional(self) -> None:
        info = DisplayInfo("Create Course", "Transform your resources into courses with AI")
        assert info.display_name == "Create Course"
        assert info.description == "Transform your resources into courses with AI"
        assert info.icon is None

    def test_icon_is_a_plain_string_name(self) -> None:
        info = DisplayInfo("Slack TA Bot", "Answer student questions in Slack", icon="slack")
        assert info.icon == "slack"

    def test_lookup_by_plugin_name(self) -> None:
        plugin = SparkthPlugin("fake-display-plugin")
        info = DisplayInfo("Fake", "A fake plugin", icon="sparkles")
        DISPLAY_INFO.add_item(plugin, info)
        assert get_plugin_display_info("fake-display-plugin") is info

    def test_lookup_returns_none_for_unknown_plugin(self) -> None:
        assert get_plugin_display_info("no-such-plugin") is None


class TestSidebarEntry:
    def test_label_is_positional(self) -> None:
        entry = SidebarEntry("Create Course", icon="plus", order=1)
        assert entry.label == "Create Course"
        assert entry.icon == "plus"
        assert entry.order == 1

    def test_icon_and_order_are_optional(self) -> None:
        entry = SidebarEntry("Somewhere")
        assert entry.icon is None
        assert isinstance(entry.order, int)

    def test_lookup_by_plugin_name(self) -> None:
        plugin = SparkthPlugin("fake-sidebar-plugin")
        entry = SidebarEntry("Fake", order=2)
        SIDEBAR_ENTRIES.add_item(plugin, entry)
        assert get_plugin_sidebar_entry("fake-sidebar-plugin") is entry

    def test_lookup_returns_none_for_unknown_plugin(self) -> None:
        assert get_plugin_sidebar_entry("no-such-plugin") is None


class TestFrontendApp:
    def test_registered_plugin_has_frontend(self) -> None:
        plugin = SparkthPlugin("fake-frontend-plugin")
        FRONTEND_APPS.add_item(plugin, FrontendApp())
        assert plugin_has_frontend("fake-frontend-plugin") is True

    def test_unregistered_plugin_has_no_frontend(self) -> None:
        assert plugin_has_frontend("backend-only-plugin") is False
