"""Shared utility helpers for Google Drive route handlers.

Functions here are called directly by route handlers — they are not
FastAPI dependencies.
"""

from typing import cast

from fastapi import HTTPException, status
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.documents.models import Document
from app.core_plugins.googledrive.config import get_googledrive_settings


async def batch_fetch_documents(session: AsyncSession, doc_ids: list[int]) -> dict[int, Document]:
    """Fetch Documents by ID. Returns mapping from document_id to Document."""
    if not doc_ids:
        return {}
    result = await session.exec(select(Document).where(col(Document.id).in_(doc_ids)))
    return {cast(int, d.id): d for d in result.all()}


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
