"""FastAPI dependencies for Google Drive route handlers.

Functions here are injected via ``Depends()`` by route handlers.
"""

from fastapi import Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.db import get_async_session
from sparkth.lib.i18n import _
from sparkth.lib.log import get_logger
from sparkth.plugins.googledrive.models import DriveFile, DriveFolder

__all__ = [
    "get_drive_file",
    "get_drive_file_owner_id",
    "get_drive_folder",
    "get_drive_folder_owner_id",
]

logger = get_logger(__name__)


async def get_drive_folder(folder_id: int, session: AsyncSession = Depends(get_async_session)) -> DriveFolder:
    """Resolve a folder id to its non-deleted record, whoever owns it. Raises 404 when there is none."""
    result = await session.exec(
        select(DriveFolder).where(
            DriveFolder.id == folder_id,
            DriveFolder.is_deleted == False,  # noqa: E712
        )
    )
    folder = result.first()
    if folder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_("Folder not found"))
    return folder


async def get_drive_file(file_id: int, session: AsyncSession = Depends(get_async_session)) -> DriveFile:
    """Resolve a file id to its non-deleted record, whoever owns it. Raises 404 when there is none."""
    result = await session.exec(
        select(DriveFile).where(
            DriveFile.id == file_id,
            DriveFile.is_deleted == False,  # noqa: E712
        )
    )
    drive_file = result.first()
    if drive_file is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_("File not found"))
    return drive_file


async def get_drive_folder_owner_id(folder: DriveFolder = Depends(get_drive_folder)) -> str:
    """Return the id of the user who owns the folder, as the object id of its ``user`` scope."""
    return str(folder.user_id)


async def get_drive_file_owner_id(drive_file: DriveFile = Depends(get_drive_file)) -> str:
    """Return the id of the user who owns the file, as the object id of its ``user`` scope."""
    return str(drive_file.user_id)
