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


class PluginNotConfiguredError(PluginError):
    """Raised when the calling user has no usable stored settings for a plugin.

    The message is shown to the chat model, so it names the plugin and tells the user where
    to add its settings.
    """

    def __init__(self, display_name: str) -> None:
        super().__init__(
            f"{display_name} is not set up for this user. "
            f"Tell them to add their {display_name} settings on the My Plugins page."
        )
