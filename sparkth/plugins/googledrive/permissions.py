"""Permissions the Google Drive plugin declares."""

from sparkth.lib.permissions import Permission

# Drive folder and file access, checked at the user scope of the record's owner.
DRIVE_READ = Permission.create("googledrive.read")
DRIVE_SYNC = Permission.create("googledrive.sync")
DRIVE_DELETE = Permission.create("googledrive.delete")
