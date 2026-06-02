"""
Sparkth Plugin System

Provides a flexible, OOP-based plugin architecture with:
- Configuration-based plugin discovery
- Plugin lifecycle management (initialize, enable, disable)
- Route registration
- Database models and migrations
- MCP tools integration
- Middleware and dependency injection
- Configuration management
"""

from app.core_plugins.canvas.config import CanvasConfig
from app.core_plugins.chat.config import ChatUserConfig
from app.core_plugins.openedx.config import OpenEdxConfig
from app.core_plugins.slack.config import SlackConfig
from app.plugins.base import SparkthPlugin
from app.plugins.config_base import PluginConfig
from app.plugins.exceptions import (
    PluginAlreadyLoadedError,
    PluginConfigError,
    PluginDependencyError,
    PluginError,
    PluginLoadError,
    PluginNotFoundError,
    PluginNotLoadedError,
    PluginValidationError,
)

from .loader import PluginLoader


def get_plugin_loader() -> PluginLoader:
    """
    Get the singleton PluginLoader instance.

    This function is safe and efficient to call multiple times.

    Returns:
        PluginLoader: The global plugin loader instance
    """
    return PluginLoader.instance()


__all__ = [
    "SparkthPlugin",
    "PluginLoader",
    "get_plugin_loader",
    "PluginError",
    "PluginNotFoundError",
    "PluginLoadError",
    "PluginValidationError",
    "PluginDependencyError",
    "PluginAlreadyLoadedError",
    "PluginNotLoadedError",
    "PluginConfigError",
]


PLUGIN_CONFIG_CLASSES: dict[str, type[PluginConfig]] = {
    "canvas": CanvasConfig,
    "open-edx": OpenEdxConfig,
    "chat": ChatUserConfig,
    "slack": SlackConfig,
}
