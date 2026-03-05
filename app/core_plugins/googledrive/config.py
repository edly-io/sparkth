"""Configuration for Google Drive plugin."""
from pydantic import Field

from app.plugins.config_base import PluginConfig


class GoogleDriveConfig(PluginConfig):
    """Google Drive plugin configuration.

    OAuth credentials are stored here. OAuth tokens are stored
    separately in the DriveOAuthToken table.
    """

    google_client_id: str = Field(default="", description="Google OAuth Client ID")
    google_client_secret: str = Field(default="", description="Google OAuth Client Secret")
    google_redirect_uri: str = Field(
        default="http://localhost:8000/api/v1/googledrive/oauth/callback",
        description="Google OAuth Redirect URI",
    )
