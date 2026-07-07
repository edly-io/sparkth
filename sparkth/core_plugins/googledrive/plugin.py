"""Google Drive plugin for Sparkth."""

import sparkth.core_plugins.googledrive.models  # noqa: F401 - registers tables in SQLModel metadata
from sparkth.core_plugins.googledrive.config import GoogleDriveConfig
from sparkth.core_plugins.googledrive.routes import router
from sparkth.lib.config.hooks import CONFIG_SCHEMAS
from sparkth.lib.plugins import SparkthPlugin
from sparkth.lib.routes import register_router


class GoogleDrivePlugin(SparkthPlugin):
    """Google Drive integration plugin.

    Provides folder sync and file management capabilities with Google Drive.
    Authentication is handled via OAuth 2.0.
    """

    def __init__(self, name: str = "google-drive"):
        super().__init__(name)
        register_router(self, router)
        CONFIG_SCHEMAS.add_item(self, GoogleDriveConfig)
