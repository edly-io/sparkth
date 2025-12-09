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

__all__ = [
    "SparkthPlugin",
    "PluginManager",
    "PluginError",
    "PluginNotFoundError",
    "PluginLoadError",
    "PluginValidationError",
    "PluginDependencyError",
    "PluginAlreadyLoadedError",
    "PluginNotLoadedError",
    "PluginConfigError",
]
