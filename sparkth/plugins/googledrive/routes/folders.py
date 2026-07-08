"""Google Drive folder endpoints."""

from datetime import datetime, timezone
from typing import cast

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.db import get_async_session
from sparkth.lib.log import get_logger
from sparkth.plugins.googledrive.client import GoogleDriveClient
from sparkth.plugins.googledrive.models import DriveFile, DriveFolder
from sparkth.plugins.googledrive.oauth import get_valid_access_token
from sparkth.plugins.googledrive.routes.dependencies import require_user_id
from sparkth.plugins.googledrive.routes.route_utils import batch_fetch_documents, get_drive_credentials
from sparkth.plugins.googledrive.schemas import (
    CreateFolderRequest,
    DriveFileResponse,
    DriveFolderResponse,
    DriveFolderWithFilesResponse,
    PaginatedResponse,
    SyncFolderRequest,
    SyncStatusResponse,
)
from sparkth.plugins.googledrive.utils import process_folder_rag

router = APIRouter()
logger = get_logger(__name__)

_FOLDER_MIME_TYPE: str = GoogleDriveClient.FOLDER_MIME_TYPE


@router.get("/folders", response_model=PaginatedResponse[DriveFolderResponse])
async def list_folders(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of items to return"),
    user_id: int = Depends(require_user_id),
    session: AsyncSession = Depends(get_async_session),
) -> PaginatedResponse[DriveFolderResponse]:
    """List synced Google Drive folders for the current user with pagination."""
    file_count_subq = (
        # mypy doesn't understand passing model columns directly to select() and group_by()
        select(DriveFile.folder_id, func.count(DriveFile.id).label("file_count"))  # type: ignore[arg-type]
        .where(DriveFile.is_deleted == False)  # noqa: E712
        .group_by(DriveFile.folder_id)  # type: ignore[arg-type]
        .subquery()
    )

    base_stmt = (
        select(DriveFolder, file_count_subq.c.file_count)
        # mypy can't verify the join condition between a model column and a subquery column
        .outerjoin(file_count_subq, DriveFolder.id == file_count_subq.c.folder_id)  # type: ignore[arg-type]
        .where(
            DriveFolder.user_id == user_id,
            DriveFolder.is_deleted == False,  # noqa: E712
        )
    )

    count_stmt = select(func.count()).select_from(
        select(DriveFolder.id)
        .where(
            DriveFolder.user_id == user_id,
            DriveFolder.is_deleted == False,  # noqa: E712
        )
        .subquery()
    )
    total = (await session.exec(count_stmt)).one()
    rows = (await session.exec(base_stmt.offset(skip).limit(limit))).all()

    return PaginatedResponse(
        items=[
            DriveFolderResponse(
                id=cast(int, folder.id),
                drive_folder_id=folder.drive_folder_id,
                name=folder.drive_folder_name,
                parent_id=folder.drive_parent_id,
                file_count=file_count or 0,
                last_synced_at=folder.last_synced_at,
                sync_status=folder.sync_status,
            )
            for folder, file_count in rows
        ],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("/folders/sync", response_model=DriveFolderResponse)
async def sync_folder(
    request: SyncFolderRequest,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(require_user_id),
    session: AsyncSession = Depends(get_async_session),
) -> DriveFolderResponse:
    """Sync an existing Google Drive folder."""
    client_id, client_secret, _ = get_drive_credentials()
    access_token = await get_valid_access_token(session, user_id, client_id, client_secret)

    result = await session.exec(
        select(DriveFolder).where(
            DriveFolder.user_id == user_id,
            DriveFolder.drive_folder_id == request.drive_folder_id,
            DriveFolder.is_deleted == False,  # noqa: E712
        )
    )
    if result.first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Folder is already synced")

    async with GoogleDriveClient(access_token) as client:
        folder_metadata = await client.get_folder(request.drive_folder_id)

    now = datetime.now(timezone.utc)
    folder = DriveFolder(
        user_id=user_id,
        drive_folder_id=folder_metadata["id"],
        drive_folder_name=folder_metadata["name"],
        drive_parent_id=folder_metadata.get("parents", [None])[0] if folder_metadata.get("parents") else None,
        last_synced_at=now,
        sync_status="syncing",
    )
    session.add(folder)
    await session.commit()
    await session.refresh(folder)

    file_count = await _sync_folder_files(session, folder, user_id, access_token)
    background_tasks.add_task(process_folder_rag, cast(int, folder.id), user_id, access_token)

    return DriveFolderResponse(
        id=cast(int, folder.id),
        drive_folder_id=folder.drive_folder_id,
        name=folder.drive_folder_name,
        parent_id=folder.drive_parent_id,
        file_count=file_count,
        last_synced_at=folder.last_synced_at,
        sync_status=folder.sync_status,
    )


@router.post("/folders", response_model=DriveFolderResponse)
async def create_folder(
    request: CreateFolderRequest,
    user_id: int = Depends(require_user_id),
    session: AsyncSession = Depends(get_async_session),
) -> DriveFolderResponse:
    """Create a new folder in Google Drive and sync it."""
    client_id, client_secret, _ = get_drive_credentials()
    access_token = await get_valid_access_token(session, user_id, client_id, client_secret)

    async with GoogleDriveClient(access_token) as client:
        folder_metadata = await client.create_folder(request.name, request.parent_id)

    now = datetime.now(timezone.utc)
    folder = DriveFolder(
        user_id=user_id,
        drive_folder_id=folder_metadata["id"],
        drive_folder_name=folder_metadata["name"],
        drive_parent_id=request.parent_id,
        last_synced_at=now,
        sync_status="synced",
    )
    session.add(folder)
    await session.commit()
    await session.refresh(folder)

    return DriveFolderResponse(
        id=cast(int, folder.id),
        drive_folder_id=folder.drive_folder_id,
        name=folder.drive_folder_name,
        parent_id=folder.drive_parent_id,
        file_count=0,
        last_synced_at=folder.last_synced_at,
        sync_status=folder.sync_status,
    )


@router.get("/folders/{folder_id}", response_model=DriveFolderWithFilesResponse)
async def get_folder(
    folder_id: int,
    user_id: int = Depends(require_user_id),
    session: AsyncSession = Depends(get_async_session),
) -> DriveFolderWithFilesResponse:
    """Get a synced folder with its files."""
    folder_result = await session.exec(
        select(DriveFolder).where(
            DriveFolder.id == folder_id,
            DriveFolder.user_id == user_id,
            DriveFolder.is_deleted == False,  # noqa: E712
        )
    )
    folder = folder_result.first()
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")

    files_result = await session.exec(
        select(DriveFile).where(
            DriveFile.folder_id == folder.id,
            DriveFile.is_deleted == False,  # noqa: E712
        )
    )
    folder_files = files_result.all()

    folder_document_ids = [f.document_id for f in folder_files if f.document_id is not None]
    folder_docs = await batch_fetch_documents(session, folder_document_ids)

    files = [
        DriveFileResponse(
            id=cast(int, f.id),
            drive_file_id=f.drive_file_id,
            document_id=f.document_id,
            name=f.name,
            mime_type=f.mime_type,
            size=f.size,
            modified_time=f.modified_time,
            last_synced_at=f.last_synced_at,
            rag_status=folder_docs[f.document_id].status if f.document_id and f.document_id in folder_docs else None,
            rag_error=folder_docs[f.document_id].error if f.document_id and f.document_id in folder_docs else None,
        )
        for f in folder_files
    ]

    return DriveFolderWithFilesResponse(
        id=cast(int, folder.id),
        drive_folder_id=folder.drive_folder_id,
        name=folder.drive_folder_name,
        parent_id=folder.drive_parent_id,
        file_count=len(files),
        last_synced_at=folder.last_synced_at,
        sync_status=folder.sync_status,
        files=files,
    )


@router.delete("/folders/{folder_id}")
async def delete_folder(
    folder_id: int,
    user_id: int = Depends(require_user_id),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, str]:
    """Remove a folder and all its files from Sparkth tracking."""
    folder_result = await session.exec(
        select(DriveFolder).where(
            DriveFolder.id == folder_id,
            DriveFolder.user_id == user_id,
            DriveFolder.is_deleted == False,  # noqa: E712
        )
    )
    folder = folder_result.first()
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")

    files_result = await session.exec(
        select(DriveFile).where(
            DriveFile.folder_id == folder.id,
            DriveFile.is_deleted == False,  # noqa: E712
        )
    )
    for f in files_result.all():
        f.soft_delete()
        session.add(f)

    folder.soft_delete()
    session.add(folder)
    await session.commit()

    return {"detail": "Folder removed from Sparkth successfully"}


@router.post("/folders/{folder_id}/refresh", response_model=SyncStatusResponse)
async def refresh_folder(
    folder_id: int,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(require_user_id),
    session: AsyncSession = Depends(get_async_session),
) -> SyncStatusResponse:
    """Refresh folder contents from Google Drive."""
    result = await session.exec(
        select(DriveFolder).where(
            DriveFolder.id == folder_id,
            DriveFolder.user_id == user_id,
            DriveFolder.is_deleted == False,  # noqa: E712
        )
    )
    folder = result.first()
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")

    client_id, client_secret, _ = get_drive_credentials()
    access_token = await get_valid_access_token(session, user_id, client_id, client_secret)

    try:
        await _sync_folder_files(session, folder, user_id, access_token)
        background_tasks.add_task(process_folder_rag, cast(int, folder.id), user_id, access_token)

        return SyncStatusResponse(
            folder_id=cast(int, folder.id),
            sync_status=folder.sync_status,
            last_synced_at=folder.last_synced_at,
        )

    except HTTPException:
        raise
    except (ConnectionError, TimeoutError, RuntimeError, ValueError, OSError) as e:
        folder.sync_status = "error"
        folder.sync_error = str(e)
        folder.update_timestamp()
        session.add(folder)
        await session.commit()
        await session.refresh(folder)

        return SyncStatusResponse(
            folder_id=cast(int, folder.id),
            sync_status="error",
            last_synced_at=folder.last_synced_at,
            error=str(e),
        )


async def _sync_folder_files(session: AsyncSession, folder: DriveFolder, user_id: int, access_token: str) -> int:
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

    result = await session.exec(
        select(DriveFile).where(
            DriveFile.folder_id == folder.id,
            DriveFile.is_deleted == False,  # noqa: E712
        )
    )
    existing_files = result.all()
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
    await session.commit()
    await session.refresh(folder)

    return len(drive_files)
