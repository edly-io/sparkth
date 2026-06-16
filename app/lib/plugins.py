"""Public API for the plugin framework.

All plugins and external modules import the plugin-authoring surface from here.
Nothing outside ``app/lib/plugins`` should import from ``app.plugins``,
``app.plugins.base``, ``app.plugins.config_base`` or ``app.plugins.middleware``
directly.
"""

from typing import TYPE_CHECKING, Any

from app.plugins import get_plugin_loader
from app.plugins.base import SparkthPlugin
from app.plugins.config_base import PluginConfig

if TYPE_CHECKING:
    from app.plugins.middleware import PluginAccessMiddleware

__all__ = ["get_plugin_loader", "PluginConfig", "SparkthPlugin", "PluginAccessMiddleware"]


def __getattr__(name: str) -> Any:
    # ``PluginAccessMiddleware`` pulls in ``app.core.routes``, which imports back
    # through ``app.lib.hooks`` -> ``app.lib.plugins``. This facade is loaded
    # during that bootstrap, so importing the middleware eagerly closes a circular
    # import. Resolve it lazily on first access, once modules are initialized.
    if name == "PluginAccessMiddleware":
        from app.plugins.middleware import PluginAccessMiddleware

        return PluginAccessMiddleware
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
