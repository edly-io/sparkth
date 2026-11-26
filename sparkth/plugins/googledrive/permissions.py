"""Permissions the Google Drive plugin declares."""

from sparkth.lib.i18n import gettext_noop
from sparkth.lib.permissions import Permission

# The category this plugin's permissions are listed under.
_CATEGORY = gettext_noop("Google Drive")

# Drive folder and file access, checked at the user scope of the record's owner.
DRIVE_READ = Permission.create(
    "googledrive.read",
    gettext_noop("See Drive folders"),
    gettext_noop("View connected folders and synced files."),
    _CATEGORY,
)
DRIVE_SYNC = Permission.create(
    "googledrive.sync",
    gettext_noop("Sync Drive folders"),
    gettext_noop("Fetch new and changed files."),
    _CATEGORY,
)
DRIVE_DELETE = Permission.create(
    "googledrive.delete",
    gettext_noop("Delete Drive files"),
    gettext_noop("Delete synced files from Sparkth."),
    _CATEGORY,
)
