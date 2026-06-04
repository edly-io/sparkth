"""Shared utility helpers for Google Drive route handlers.

Functions here are called directly by route handlers — they are not
FastAPI dependencies.
"""

from fastapi import HTTPException, status

from app.core.config import get_settings
from app.core_plugins.googledrive.config import get_googledrive_settings


def get_drive_credentials() -> tuple[str, str, str]:
    """Return Google OAuth credentials for the Drive plugin.

    Reads ``GOOGLE_CLIENT_ID`` and ``GOOGLE_CLIENT_SECRET`` from core settings
    and ``GOOGLE_DRIVE_REDIRECT_URI`` from the plugin settings.

    Returns:
        Tuple of (client_id, client_secret, redirect_uri)

    Raises:
        HTTPException: 400 if GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET are not set
    """
    settings = get_settings()
    client_id = settings.GOOGLE_CLIENT_ID
    client_secret = settings.GOOGLE_CLIENT_SECRET
    redirect_uri = get_googledrive_settings().GOOGLE_DRIVE_REDIRECT_URI

    if not client_id or not client_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google Drive credentials not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.",
        )

    return client_id, client_secret, redirect_uri
