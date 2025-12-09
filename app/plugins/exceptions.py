"""
Plugin-related exceptions for the Sparkth plugin system.
"""


class PluginError(Exception):
    """Base exception for all plugin-related errors."""

    pass


class PluginNotFoundError(PluginError):
    """Raised when a plugin cannot be found."""

    pass


class PluginLoadError(PluginError):
    """Raised when a plugin fails to load."""

    pass


class PluginValidationError(PluginError):
    """Raised when a plugin fails validation."""

    pass


class PluginDependencyError(PluginError):
    """Raised when plugin dependencies cannot be resolved."""

    pass


class PluginAlreadyLoadedError(PluginError):
    """Raised when attempting to load an already loaded plugin."""

    pass


class PluginNotLoadedError(PluginError):
    """Raised when attempting to operate on a plugin that isn't loaded."""

    pass


class PluginConfigError(PluginError):
    """Raised when plugin configuration is invalid."""

    pass
