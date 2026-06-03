"""Shared utility helpers for Google Drive route handlers.

Functions here are called directly by route handlers — they are not
FastAPI dependencies.
"""

from datetime import datetime, timezone
from typing import cast

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.core.config import get_settings
from app.core_plugins.googledrive.client import GoogleDriveClient
from app.core_plugins.googledrive.config import get_googledrive_settings
from app.models.drive import DriveFile, DriveFolder
from app.rag.types import RagStatus

_FOLDER_MIME_TYPE: str = GoogleDriveClient.FOLDER_MIME_TYPE


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


async def _sync_folder_files(session: Session, folder: DriveFolder, user_id: int, access_token: str) -> int:
    """Sync a folder's files from the Drive API into the database.

    Fetches the current file list from Drive, upserts new or changed files,
    and soft-deletes any local records whose Drive counterpart has been removed.

    Returns:
        Number of active (non-deleted) files after sync.
    """
    async with GoogleDriveClient(access_token) as client:
        drive_files_data = await client.list_files(folder_id=folder.drive_folder_id)

    now = datetime.now(timezone.utc)
    drive_files = [f for f in drive_files_data.get("files", []) if f.get("mimeType") != _FOLDER_MIME_TYPE]
    drive_file_ids = {f["id"] for f in drive_files}

    existing_files = session.exec(
        select(DriveFile).where(
            DriveFile.folder_id == folder.id,
            DriveFile.is_deleted == False,  # noqa: E712
        )
    ).all()
    existing_map = {f.drive_file_id: f for f in existing_files}

    for df in drive_files:
        modified_time = None
        if df.get("modifiedTime"):
            modified_time = datetime.fromisoformat(df["modifiedTime"].replace("Z", "+00:00"))

        if df["id"] in existing_map:
            existing_file = existing_map[df["id"]]
            existing_file.name = df["name"]
            existing_file.mime_type = df.get("mimeType")
            existing_file.size = int(df["size"]) if df.get("size") else None
            existing_file.md5_checksum = df.get("md5Checksum")
            existing_file.modified_time = modified_time
            existing_file.last_synced_at = now
            existing_file.update_timestamp()
            session.add(existing_file)
        else:
            new_file = DriveFile(
                folder_id=cast(int, folder.id),
                user_id=user_id,
                drive_file_id=df["id"],
                name=df["name"],
                mime_type=df.get("mimeType"),
                size=int(df["size"]) if df.get("size") else None,
                md5_checksum=df.get("md5Checksum"),
                modified_time=modified_time,
                last_synced_at=now,
                rag_status=RagStatus.QUEUED,
            )
            session.add(new_file)

    for file_id, existing_file in existing_map.items():
        if file_id not in drive_file_ids:
            existing_file.soft_delete()
            session.add(existing_file)

    folder.last_synced_at = now
    folder.sync_status = "synced"
    folder.sync_error = None
    folder.update_timestamp()
    session.add(folder)
    session.commit()
    session.refresh(folder)

    return len(drive_files)
