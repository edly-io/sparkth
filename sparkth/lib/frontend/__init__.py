"""Lookup helpers over the frontend-facing plugin declaration hooks.

Like ``sparkth.lib.config``, the hooks are populated when plugins are
instantiated at the process entrypoint; these helpers assume that has already
happened and resolve declarations by plugin name.
"""

from sparkth.lib.frontend.hooks import DISPLAY_INFO, FRONTEND_APPS, SIDEBAR_ENTRIES, DisplayInfo, SidebarEntry


def get_plugin_display_info(plugin_name: str) -> DisplayInfo | None:
    """Return the display info a plugin declared, looked up by plugin name."""
    for plugin, info in DISPLAY_INFO.iter_items():
        if plugin.name == plugin_name:
            return info
    return None


def get_plugin_sidebar_entry(plugin_name: str) -> SidebarEntry | None:
    """Return the sidebar entry a plugin declared, looked up by plugin name."""
    for plugin, entry in SIDEBAR_ENTRIES.iter_items():
        if plugin.name == plugin_name:
            return entry
    return None


def plugin_has_frontend(plugin_name: str) -> bool:
    """Return whether a plugin declared that it ships a frontend page."""
    return any(plugin.name == plugin_name for plugin, _ in FRONTEND_APPS.iter_items())
