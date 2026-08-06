"""Hooks for the frontend-facing metadata a plugin declares.

The backend is the single source of truth for what the frontend shows about a
plugin. Each concern is its own hook, mirroring ``CONFIG_SCHEMAS`` and
``MCP_TOOLS``, rather than one monolithic manifest object:

- :data:`DISPLAY_INFO`: the human-facing identity (display name, description,
  optional icon) shown in settings and catalogs. Every plugin should register
  one; without it the plugin appears with only its slug name.
- :data:`SIDEBAR_ENTRIES`: the dashboard sidebar navigation entry (label,
  optional icon, sort order). Register it only if the plugin should appear in
  the sidebar.
- :data:`FRONTEND_APPS`: marks the plugin as shipping a frontend page at
  ``/dashboard/<plugin-name>``. Backend-only plugins skip it.

A plugin registers from its ``__init__``, passing human-facing names
positionally::

    DISPLAY_INFO.add_item(self, DisplayInfo("Create Course", "Build courses with AI", icon="plus"))
    SIDEBAR_ENTRIES.add_item(self, SidebarEntry("Create Course", icon="plus", order=1))
    FRONTEND_APPS.add_item(self, FrontendApp())

Icons cross the wire as `lucide <https://lucide.dev/icons/>`_ icon names, never
as components; the frontend resolves names to components.

The declarations are exposed read-only on the user-plugins API (``display``,
``sidebar``, and ``has_frontend`` on ``UserPluginResponse``), so the frontend
renders what the backend declares instead of keeping its own copy.
"""

from dataclasses import dataclass

from sparkth.lib.hooks import PluginHook


@dataclass(frozen=True)
class DisplayInfo:
    """The human-facing identity of a plugin, shown in settings and catalogs."""

    display_name: str
    description: str
    icon: str | None = None


@dataclass(frozen=True)
class SidebarEntry:
    """A dashboard sidebar navigation entry pointing at the plugin's frontend page.

    ``order`` sorts entries ascending; entries that keep the default sort last.
    """

    label: str
    icon: str | None = None
    order: int = 100


@dataclass(frozen=True)
class FrontendApp:
    """Marks the plugin as shipping a frontend page (``/dashboard/<plugin-name>``).

    Registering it is the declaration. The marker carries no data yet; fields
    describing the frontend counterpart (entry route, bundle info) belong here
    as the frontend plugin system grows.
    """


# The display info contributed by each plugin (one per plugin).
DISPLAY_INFO: PluginHook[DisplayInfo] = PluginHook()

# The sidebar entry contributed by each plugin (one per plugin; register only if
# the plugin should appear in the dashboard sidebar).
SIDEBAR_ENTRIES: PluginHook[SidebarEntry] = PluginHook()

# The frontend-app marker contributed by each plugin that ships a frontend page.
FRONTEND_APPS: PluginHook[FrontendApp] = PluginHook()
