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
from app.plugins.base import SparkthPlugin
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

from .manager import PluginManager

# Global plugin manager instance
_plugin_manager_instance: PluginManager | None = None


def get_plugin_manager() -> PluginManager:
    """
    Get the singleton PluginManager instance.

    Returns:
        PluginManager: The global plugin manager instance
    """
    global _plugin_manager_instance
    if _plugin_manager_instance is None:
        _plugin_manager_instance = PluginManager()
    return _plugin_manager_instance


__all__ = [
    "SparkthPlugin",
    "PluginManager",
    "get_plugin_manager",
    "PluginError",
    "PluginNotFoundError",
    "PluginLoadError",
    "PluginValidationError",
    "PluginDependencyError",
    "PluginAlreadyLoadedError",
    "PluginNotLoadedError",
    "PluginConfigError",
]


PLUGIN_CONFIG_CLASSES = {"canvas": CanvasConfig, "open-edx": OpenEdxConfig, "chat": ChatUserConfig}
