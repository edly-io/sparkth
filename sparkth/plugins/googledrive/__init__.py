"""Google Drive plugin for Sparkth."""

from pathlib import Path

from sparkth.lib.i18n import LOCALE_DIRS
from sparkth.plugins.googledrive.plugin import GoogleDrivePlugin

LOCALE_DIRS.add_item(Path(__file__).parent / "locale")

__all__ = ["GoogleDrivePlugin"]
