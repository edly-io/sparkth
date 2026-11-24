"""Response models for the plugin framework."""

from typing import Any

import pydantic

from sparkth.core.plugins.widgets import secret_field_names
from sparkth.lib.encryption import mask_secret
from sparkth.lib.frontend import get_plugin_display_info, get_plugin_sidebar_entry, plugin_has_frontend
from sparkth.lib.frontend.hooks import DisplayInfo, SidebarEntry
from sparkth.lib.i18n import gettext as translate


class PluginResponse(pydantic.BaseModel):
    """Response model for one plugin as the calling user sees it.

    ``display``, ``sidebar``, and ``has_frontend`` carry the read-only
    frontend-facing metadata the plugin declared through the
    ``sparkth.lib.frontend`` hooks; build responses with :meth:`for_plugin`
    so they are always populated.

    ``enabled`` is the calling user's own preference for the plugin; ``system_enabled`` is the
    system-wide switch, which applies to every user.

    ``config_schema`` is the plugin's declared JSON schema, which the settings
    UI renders its form from -- field types, labels, defaults, and the widget
    hints a plugin sets through ``json_schema_extra``. It is empty for a plugin
    that registered no config class.

    ``config`` never carries a field marked ``secret()``; ``secrets_set`` names the ones stored,
    and ``masked_secrets`` maps each stored ``secret(masked=True)`` field to its masked value.
    """

    plugin_name: str
    enabled: bool
    system_enabled: bool
    config: dict[str, Any]
    secrets_set: list[str] = []
    masked_secrets: dict[str, str] = {}
    is_core: bool
    config_schema: dict[str, Any] = {}
    display: DisplayInfo | None = None
    sidebar: SidebarEntry | None = None
    has_frontend: bool = False

    @classmethod
    def for_plugin(
        cls,
        plugin_name: str,
        enabled: bool,
        system_enabled: bool,
        config: dict[str, Any],
        is_core: bool,
        config_schema: dict[str, Any] | None = None,
    ) -> "PluginResponse":
        """Build a response carrying the frontend metadata declared for ``plugin_name``.

        The declared display and sidebar strings are ``gettext_noop``-marked
        source messages; this is their rendering boundary, so they are
        translated into the request locale here.
        """
        display = get_plugin_display_info(plugin_name)
        if display is not None:
            display = DisplayInfo(translate(display.display_name), translate(display.description), display.icon)
        sidebar = get_plugin_sidebar_entry(plugin_name)
        if sidebar is not None:
            sidebar = SidebarEntry(translate(sidebar.label), sidebar.icon, sidebar.order)
        properties = (config_schema or {}).get("properties", {})
        secrets = secret_field_names(config_schema or {})
        return cls(
            plugin_name=plugin_name,
            enabled=enabled,
            system_enabled=system_enabled,
            config={key: value for key, value in config.items() if key not in secrets},
            secrets_set=[name for name in secrets if config.get(name)],
            masked_secrets={
                name: mask_secret(config[name])
                for name in secrets
                if config.get(name) and properties[name].get("masked")
            },
            is_core=is_core,
            config_schema=config_schema or {},
            display=display,
            sidebar=sidebar,
            has_frontend=plugin_has_frontend(plugin_name),
        )
