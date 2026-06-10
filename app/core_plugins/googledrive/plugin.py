"""Google Drive plugin for Sparkth."""

import app.core_plugins.googledrive.models  # noqa: F401 - registers tables in SQLModel metadata
from app.core_plugins.googledrive.config import GoogleDriveConfig
from app.core_plugins.googledrive.routes import router
from app.plugins.base import SparkthPlugin


class GoogleDrivePlugin(SparkthPlugin):
    """Google Drive integration plugin.

    Provides folder sync and file management capabilities with Google Drive.
    Authentication is handled via OAuth 2.0.
    """

    def __init__(self, name: str = "google-drive"):
        super().__init__(name=name, config_schema=GoogleDriveConfig)
        self.add_route(router)

    def get_route_prefix(self) -> str:
        """Return the route prefix for Google Drive endpoints."""
        return "/api/v1/googledrive"

    def get_route_tags(self) -> list[str]:
        """Return OpenAPI tags for Google Drive routes."""
        return ["Google Drive"]
