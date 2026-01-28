"""Configuration for Google Drive plugin."""

from app.plugins.config_base import PluginConfig


class GoogleDriveConfig(PluginConfig):
    """
    Google Drive plugin configuration.

    Note: OAuth tokens are stored separately in the DriveOAuthToken table,
    not in the plugin config. This config is for any user-level preferences.
    """

    pass
