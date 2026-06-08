"""
Plugin-related exceptions for the Sparkth plugin system.
"""


class PluginError(Exception):
    """Base exception for all plugin-related errors."""

    pass


class PluginLoadError(PluginError):
    """Raised when a plugin fails to load."""

    pass


class PluginValidationError(PluginError):
    """Raised when a plugin fails validation."""

    pass
