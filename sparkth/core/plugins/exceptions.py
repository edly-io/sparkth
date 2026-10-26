"""
Plugin-related exceptions for the Sparkth plugin system.
"""

from sparkth.core.plugins.constants import PLUGIN_SETTINGS_PAGE_NAME


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
    """Raised when the calling user has saved no settings for a plugin.

    The message is shown to the chat model, so it names the plugin and tells the user where
    to add its settings.
    """

    def __init__(self, display_name: str) -> None:
        super().__init__(
            f"{display_name} is not set up for this user. "
            f"Tell them to add their {display_name} settings on the {PLUGIN_SETTINGS_PAGE_NAME} page."
        )


class PluginConfigInvalidError(PluginError):
    """Raised when the calling user's saved settings for a plugin no longer validate.

    The message is shown to the chat model, so it names the plugin and tells the user where
    to update its settings.
    """

    def __init__(self, display_name: str) -> None:
        super().__init__(
            f"The saved {display_name} settings for this user are no longer valid. "
            f"Tell them to update their {display_name} settings on the {PLUGIN_SETTINGS_PAGE_NAME} page."
        )
