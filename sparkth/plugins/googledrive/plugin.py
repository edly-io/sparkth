"""Google Drive plugin for Sparkth."""

from fastapi import status

import sparkth.plugins.googledrive.models  # noqa: F401 - registers tables in SQLModel metadata
from sparkth.lib.analytics import register_event_schemas
from sparkth.lib.config.hooks import CONFIG_SCHEMAS
from sparkth.lib.exceptions.handlers import register_exception_handler
from sparkth.lib.frontend.hooks import (
    DISPLAY_INFO,
    FRONTEND_APPS,
    SIDEBAR_ENTRIES,
    DisplayInfo,
    FrontendApp,
    SidebarEntry,
)
from sparkth.lib.i18n import gettext_noop
from sparkth.lib.plugins import SparkthPlugin
from sparkth.lib.routes import register_router
from sparkth.plugins.googledrive.analytics import events
from sparkth.plugins.googledrive.config import GoogleDriveConfig
from sparkth.plugins.googledrive.exceptions import DriveNotConnected
from sparkth.plugins.googledrive.routes import router

register_exception_handler(DriveNotConnected, status.HTTP_409_CONFLICT)


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
        SIDEBAR_ENTRIES.add_item(self, SidebarEntry(gettext_noop("Resources"), icon="folder", order=4))
        FRONTEND_APPS.add_item(self, FrontendApp())
        register_event_schemas(self, events)
