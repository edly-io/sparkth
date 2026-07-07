"""Public API for the plugin framework.

All plugins and external modules import the plugin-authoring surface from here.
Nothing outside ``app/lib/plugins`` should import from ``sparkth.core.plugins``,
``sparkth.core.plugins.base``, ``sparkth.core.plugins.config_base`` or ``sparkth.core.plugins.middleware``
directly.
"""

from typing import TYPE_CHECKING, Any

from sparkth.core.plugins import get_plugin_loader
from sparkth.core.plugins.base import SparkthPlugin
from sparkth.core.plugins.config_base import PluginConfig

if TYPE_CHECKING:
    from sparkth.core.plugins.middleware import PluginAccessMiddleware

__all__ = ["get_plugin_loader", "PluginConfig", "SparkthPlugin", "PluginAccessMiddleware"]


def __getattr__(name: str) -> Any:
    # ``PluginAccessMiddleware`` pulls in ``sparkth.core.routes``, which imports back
    # through ``sparkth.lib.hooks`` -> ``sparkth.lib.plugins``. This facade is loaded
    # during that bootstrap, so importing the middleware eagerly closes a circular
    # import. Resolve it lazily on first access, once modules are initialized.
    if name == "PluginAccessMiddleware":
        from sparkth.core.plugins.middleware import PluginAccessMiddleware

        return PluginAccessMiddleware
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
