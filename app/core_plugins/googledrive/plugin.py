"""Google Drive plugin for Sparkth."""

from app.core_plugins.googledrive.config import GoogleDriveConfig
from app.core_plugins.googledrive.routes import router
from app.lib.routes.hooks import ROUTES
from app.plugins.base import SparkthPlugin


class GoogleDrivePlugin(SparkthPlugin):
    """Google Drive integration plugin.

    Provides folder sync and file management capabilities with Google Drive.
    Authentication is handled via OAuth 2.0.
    """

    def __init__(self, name: str = "google-drive"):
        super().__init__(name=name, config_schema=GoogleDriveConfig)
        ROUTES.add_item(self, (router, "/api/v1/googledrive", ["Google Drive"]))
