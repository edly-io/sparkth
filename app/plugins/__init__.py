"""
Sparkth Plugin System

Provides a flexible, OOP-based plugin architecture with:
- Configuration-based plugin discovery
- Plugin lifecycle management (initialize, enable, disable)
- Route registration
- Database models and migrations
- MCP tools integration
- Dependency injection
- Configuration management
"""

from app.plugins.base import SparkthPlugin
from app.plugins.exceptions import (
    PluginError,
    PluginLoadError,
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
    "PluginLoadError",
    "PluginValidationError",
]
