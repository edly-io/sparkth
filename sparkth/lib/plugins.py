"""Public API for the plugin framework.

All plugins and external modules import the plugin-authoring surface from here.
Nothing outside ``sparkth/lib/plugins`` should import from ``sparkth.core.plugins`` or its
submodules directly.
"""

from typing import TYPE_CHECKING, Any

from sparkth.core.plugins import get_plugin_loader
from sparkth.core.plugins.base import SparkthPlugin
from sparkth.core.plugins.config_base import PluginConfig
from sparkth.core.plugins.exceptions import (
    ConfigValidationError,
    PluginConfigInvalidError,
    PluginConfigUnavailable,
    PluginDisabledError,
    PluginNotConfiguredError,
)
from sparkth.core.plugins.widgets import ConfigWidget, secret, widget

if TYPE_CHECKING:
    from sparkth.core.plugins.middleware import PluginAccessMiddleware
    from sparkth.core.plugins.schemas import PluginResponse
    from sparkth.core.plugins.service import (
        PluginService,
        disabled_plugin_names,
        get_disabled_plugins,
        get_plugin_service,
        load_plugin_config,
    )

__all__ = [
    "get_plugin_loader",
    "ConfigWidget",
    "PluginConfig",
    "widget",
    "secret",
    "SparkthPlugin",
    "PluginAccessMiddleware",
    "PluginService",
    "get_plugin_service",
    "ConfigValidationError",
    "PluginConfigUnavailable",
    "PluginDisabledError",
    "PluginResponse",
    "disabled_plugin_names",
    "get_disabled_plugins",
    "load_plugin_config",
    "PluginNotConfiguredError",
    "PluginConfigInvalidError",
]

# PluginService lives in ``sparkth.core.plugins.service``; it is re-exported here so
# plugins consume it through this facade. It, ``PluginResponse`` and ``PluginAccessMiddleware``
# are resolved lazily to avoid import cycles: the service pulls in ``sparkth.lib.config``
# (which imports this facade), the response model pulls in ``sparkth.lib.frontend`` and the
# middleware pulls in ``sparkth.core.routes`` (which imports back through
# ``sparkth.lib.hooks`` -> this facade). Deferring the import to first access lets this
# module finish initializing first.
_SERVICE_EXPORTS = {
    "PluginService",
    "get_plugin_service",
    "disabled_plugin_names",
    "get_disabled_plugins",
    "load_plugin_config",
}


def __getattr__(name: str) -> Any:
    if name == "PluginAccessMiddleware":
        from sparkth.core.plugins.middleware import PluginAccessMiddleware

        return PluginAccessMiddleware
    if name == "PluginResponse":
        from sparkth.core.plugins.schemas import PluginResponse

        return PluginResponse
    if name in _SERVICE_EXPORTS:
        from sparkth.core.plugins import service

        return getattr(service, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
