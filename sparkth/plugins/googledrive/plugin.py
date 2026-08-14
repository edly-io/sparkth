"""Google Drive plugin for Sparkth."""

import sparkth.plugins.googledrive.models  # noqa: F401 - registers tables in SQLModel metadata
from sparkth.lib.config.hooks import CONFIG_SCHEMAS
from sparkth.lib.frontend.hooks import DISPLAY_INFO, FRONTEND_APPS, DisplayInfo, FrontendApp
from sparkth.lib.i18n import gettext_noop
from sparkth.lib.plugins import SparkthPlugin
from sparkth.lib.routes import register_router
from sparkth.plugins.googledrive.config import GoogleDriveConfig
from sparkth.plugins.googledrive.routes import router


class GoogleDrivePlugin(SparkthPlugin):
    """Google Drive integration plugin.

    Provides folder sync and file management capabilities with Google Drive.
    Authentication is handled via OAuth 2.0.
    """

    def __init__(self) -> None:
        super().__init__("google-drive")
        register_router(self, router)
        CONFIG_SCHEMAS.add_item(self, GoogleDriveConfig)
        DISPLAY_INFO.add_item(
            self,
            DisplayInfo(gettext_noop("Google Drive"), gettext_noop("All imported files from your connected plugins")),
        )
        # Ships a frontend page but no sidebar entry.
        FRONTEND_APPS.add_item(self, FrontendApp())
