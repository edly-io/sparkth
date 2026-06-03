"""Google Drive plugin for Sparkth."""

from app.core_plugins.googledrive.config import GoogleDriveConfig
from app.core_plugins.googledrive.routes import router
from app.lib.config.hooks import CONFIG_SCHEMAS
from app.lib.routes.hooks import ROUTES
from app.plugins.base import SparkthPlugin


class GoogleDrivePlugin(SparkthPlugin):
    """Google Drive integration plugin.

    Provides folder sync and file management capabilities with Google Drive.
    Authentication is handled via OAuth 2.0.
    """

    def __init__(self, name: str = "google-drive"):
        super().__init__(
            name=name,
            is_core=True,
            version="1.0.0",
            description="Google Drive integration for folder sync and file management",
            author="Sparkth Team",
        )
        CONFIG_SCHEMAS.add_item(self, GoogleDriveConfig)
        ROUTES.add_item(self, ("/api/v1/googledrive", ["Google Drive"], router))
