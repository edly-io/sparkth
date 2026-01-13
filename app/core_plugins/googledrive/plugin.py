"""Google Drive plugin for Sparkth."""

from app.core_plugins.googledrive.config import GoogleDriveConfig
from app.plugins.base import SparkthPlugin


class GoogleDrivePlugin(SparkthPlugin):
    """
    Google Drive integration plugin.

    Provides folder sync and file management capabilities with Google Drive.
    Authentication is handled via OAuth 2.0.
    """

    def __init__(self, name: str = "googledrive"):
        super().__init__(
            name=name,
            config_schema=GoogleDriveConfig,
            is_core=True,
            version="1.0.0",
            description="Google Drive integration for folder sync and file management",
            author="Sparkth Team",
        )

    def initialize(self) -> None:
        """Initialize the Google Drive plugin."""
        super().initialize()

    def enable(self) -> None:
        """Enable the Google Drive plugin."""
        super().enable()

    def disable(self) -> None:
        """Disable the Google Drive plugin."""
        super().disable()
