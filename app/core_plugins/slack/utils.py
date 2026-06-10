"""Slack plugin utility helpers."""

from __future__ import annotations

from app.core_plugins.googledrive.models import DriveFile
from app.rag import constants


def resolve_source_name(drive_file: DriveFile) -> str:
    """Return the source name used for Slack source filtering."""
    filename = drive_file.name
    mime_type = drive_file.mime_type or ""
    if mime_type in constants.GOOGLE_NATIVE_MIMES and not filename.lower().endswith(".pdf"):
        filename = f"{filename}.pdf"
    return filename
