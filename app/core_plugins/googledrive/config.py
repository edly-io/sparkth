"""Configuration for Google Drive plugin."""
from app.plugins.config_base import PluginConfig


class GoogleDriveConfig(PluginConfig):
    """Google Drive plugin configuration.

    OAuth credentials (client_id, client_secret, redirect_uri) are
    app-level settings in core/config.py, not per-plugin config.
    OAuth tokens are stored per-user in the DriveOAuthToken table.
    """
