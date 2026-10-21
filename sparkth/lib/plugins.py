"""Public API for the plugin framework.

All plugins and external modules import the plugin-authoring surface from here.
Nothing outside ``sparkth/lib/plugins`` should import from ``sparkth.core.plugins``,
``sparkth.core.plugins.base``, ``sparkth.core.plugins.config_base``,
``sparkth.core.plugins.middleware`` or ``sparkth.core.plugins.service`` directly.
"""

from typing import TYPE_CHECKING, Any

from sparkth.core.plugins import get_plugin_loader
from sparkth.core.plugins.base import SparkthPlugin
from sparkth.core.plugins.config_base import ConfigAdapter, PluginConfig
from sparkth.core.plugins.exceptions import PluginNotConfiguredError
from sparkth.core.plugins.widgets import ConfigWidget, widget

if TYPE_CHECKING:
    from sparkth.core.plugins.middleware import PluginAccessMiddleware
    from sparkth.core.plugins.service import (
        ConfigValidationError,
        InternalServerError,
        PluginDisabledError,
        PluginService,
        UserPluginResponse,
        disabled_plugin_names,
        get_disabled_plugins,
        get_plugin_service,
        load_user_plugin_config,
    )

__all__ = [
    "get_plugin_loader",
    "ConfigAdapter",
    "ConfigWidget",
    "PluginConfig",
    "widget",
    "SparkthPlugin",
    "PluginAccessMiddleware",
    "PluginService",
    "get_plugin_service",
    "ConfigValidationError",
    "InternalServerError",
    "PluginDisabledError",
    "UserPluginResponse",
    "disabled_plugin_names",
    "get_disabled_plugins",
    "load_user_plugin_config",
    "PluginNotConfiguredError",
]

# PluginService lives in ``sparkth.core.plugins.service``; it is re-exported here so
# plugins consume it through this facade. Both it and ``PluginAccessMiddleware`` are
# resolved lazily to avoid import cycles: the service pulls in ``sparkth.lib.config``
# (which imports this facade) and the middleware pulls in ``sparkth.core.routes``
# (which imports back through ``sparkth.lib.hooks`` -> this facade). Deferring the
# import to first access lets this module finish initializing first.
_SERVICE_EXPORTS = {
    "PluginService",
    "get_plugin_service",
    "ConfigValidationError",
    "InternalServerError",
    "PluginDisabledError",
    "UserPluginResponse",
    "disabled_plugin_names",
    "get_disabled_plugins",
    "load_user_plugin_config",
}


def __getattr__(name: str) -> Any:
    if name == "PluginAccessMiddleware":
        from sparkth.core.plugins.middleware import PluginAccessMiddleware

        return PluginAccessMiddleware
    if name in _SERVICE_EXPORTS:
        from sparkth.core.plugins import service

        return getattr(service, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
