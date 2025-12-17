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
from app.plugins.manager import PluginManager

# Global plugin manager instance
_plugin_manager_instance = None


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
