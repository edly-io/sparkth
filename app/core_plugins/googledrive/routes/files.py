"""Google Drive file endpoints."""

import logging
import re
import urllib.parse
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlmodel import Session, select

from app.core.db import get_session
from app.core_plugins.googledrive.client import GoogleDriveClient
from app.core_plugins.googledrive.constants import DRIVE_MAX_UPLOAD_BYTES
from app.core_plugins.googledrive.routes.deps import (
    get_drive_credentials,
    get_valid_access_token,
    require_user_id,
)
from app.core_plugins.googledrive.types import (
    DriveBrowseItem,
    DriveBrowseResponse,
    DriveFileResponse,
    FileRagStatusResponse,
    FolderRagStatusResponse,
    PaginatedResponse,
    RenameFileRequest,
)
from app.models.drive import DriveFile, DriveFolder
from app.rag.types import RagStatus

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/folders/{folder_id}/files", response_model=PaginatedResponse[DriveFileResponse])
def list_files(
    folder_id: int,
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of items to return"),
    user_id: int = Depends(require_user_id),
    session: Session = Depends(get_session),
) -> PaginatedResponse[DriveFileResponse]:
    """List files in a synced folder with pagination."""
    folder = session.exec(
        select(DriveFolder).where(
            DriveFolder.id == folder_id,
            DriveFolder.user_id == user_id,
            DriveFolder.is_deleted == False,  # noqa: E712
        )
    ).first()
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")

    base_query = select(DriveFile).where(
        DriveFile.folder_id == folder_id,
        DriveFile.is_deleted == False,  # noqa: E712
    )

    total = session.exec(select(func.count()).select_from(base_query.subquery())).one()
    files = session.exec(base_query.offset(skip).limit(limit)).all()

    return PaginatedResponse(
        items=[
            DriveFileResponse(
                id=f.id,  # type: ignore[arg-type]
                drive_file_id=f.drive_file_id,
                name=f.name,
                mime_type=f.mime_type,
                size=f.size,
                modified_time=f.modified_time,
                last_synced_at=f.last_synced_at,
                rag_status=f.rag_status,
                rag_error=f.rag_error,
            )
            for f in files
        ],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("/folders/{folder_id}/files", response_model=DriveFileResponse)
async def upload_file(
    folder_id: int,
    file: UploadFile = File(...),
    user_id: int = Depends(require_user_id),
    session: Session = Depends(get_session),
) -> DriveFileResponse:
    """Upload a file to a Google Drive folder."""
    folder = session.exec(
        select(DriveFolder).where(
            DriveFolder.id == folder_id,
            DriveFolder.user_id == user_id,
            DriveFolder.is_deleted == False,  # noqa: E712
        )
    ).first()
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")

    client_id, client_secret, _ = get_drive_credentials()
    access_token = await get_valid_access_token(session, user_id, client_id, client_secret)

    content = await file.read()
    if len(content) > DRIVE_MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File size exceeds 30MB limit."
        )
    mime_type = file.content_type or "application/octet-stream"

    async with GoogleDriveClient(access_token) as client:
        file_metadata = await client.upload_file(
            name=file.filename or "untitled",
            content=content,
            mime_type=mime_type,
            folder_id=folder.drive_folder_id,
        )

    now = datetime.now(timezone.utc)
    modified_time = None
    if file_metadata.get("modifiedTime"):
        modified_time = datetime.fromisoformat(file_metadata["modifiedTime"].replace("Z", "+00:00"))

    drive_file = DriveFile(
        folder_id=folder.id,  # type: ignore[arg-type]
        user_id=user_id,
        drive_file_id=file_metadata["id"],
        name=file_metadata["name"],
        mime_type=file_metadata.get("mimeType"),
        size=int(file_metadata["size"]) if file_metadata.get("size") else len(content),
        md5_checksum=file_metadata.get("md5Checksum"),
        modified_time=modified_time,
        last_synced_at=now,
        rag_status=RagStatus.QUEUED,
    )
    session.add(drive_file)
    session.commit()
    session.refresh(drive_file)

    return DriveFileResponse(
        id=drive_file.id,  # type: ignore[arg-type]
        drive_file_id=drive_file.drive_file_id,
        name=drive_file.name,
        mime_type=drive_file.mime_type,
        size=drive_file.size,
        modified_time=drive_file.modified_time,
        last_synced_at=drive_file.last_synced_at,
        rag_status=drive_file.rag_status,
        rag_error=drive_file.rag_error,
    )


@router.get("/files/{file_id}", response_model=DriveFileResponse)
def get_file(
    file_id: int,
    user_id: int = Depends(require_user_id),
    session: Session = Depends(get_session),
) -> DriveFileResponse:
    """Get file metadata."""
    drive_file = session.exec(
        select(DriveFile).where(
            DriveFile.id == file_id,
            DriveFile.user_id == user_id,
            DriveFile.is_deleted == False,  # noqa: E712
        )
    ).first()
    if not drive_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    return DriveFileResponse(
        id=drive_file.id,  # type: ignore[arg-type]
        drive_file_id=drive_file.drive_file_id,
        name=drive_file.name,
        mime_type=drive_file.mime_type,
        size=drive_file.size,
        modified_time=drive_file.modified_time,
        last_synced_at=drive_file.last_synced_at,
        rag_status=drive_file.rag_status,
        rag_error=drive_file.rag_error,
    )


@router.get("/files/{file_id}/rag-status", response_model=FileRagStatusResponse)
def get_file_rag_status(
    file_id: int,
    user_id: int = Depends(require_user_id),
    session: Session = Depends(get_session),
) -> FileRagStatusResponse:
    """Get the RAG processing status for a single file."""
    drive_file = session.exec(
        select(DriveFile).where(
            DriveFile.id == file_id,
            DriveFile.user_id == user_id,
            DriveFile.is_deleted == False,  # noqa: E712
        )
    ).first()
    if not drive_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    return FileRagStatusResponse(
        file_id=drive_file.id,  # type: ignore[arg-type]
        name=drive_file.name,
        rag_status=drive_file.rag_status,
        rag_error=drive_file.rag_error,
    )


@router.get("/folders/{folder_id}/rag-status", response_model=FolderRagStatusResponse)
def get_folder_rag_status(
    folder_id: int,
    user_id: int = Depends(require_user_id),
    session: Session = Depends(get_session),
) -> FolderRagStatusResponse:
    """Get the RAG processing status for all files in a folder."""
    folder = session.exec(
        select(DriveFolder).where(
            DriveFolder.id == folder_id,
            DriveFolder.user_id == user_id,
            DriveFolder.is_deleted == False,  # noqa: E712
        )
    ).first()
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")

    files = session.exec(
        select(DriveFile).where(
            DriveFile.folder_id == folder_id,
            DriveFile.is_deleted == False,  # noqa: E712
        )
    ).all()

    return FolderRagStatusResponse(
        folder_id=folder_id,
        files=[
            FileRagStatusResponse(
                file_id=f.id,  # type: ignore[arg-type]
                name=f.name,
                rag_status=f.rag_status,
                rag_error=f.rag_error,
            )
            for f in files
        ],
    )


@router.get("/files/{file_id}/download")
async def download_file(
    file_id: int,
    user_id: int = Depends(require_user_id),
    session: Session = Depends(get_session),
) -> StreamingResponse:
    """Download a file from Google Drive."""
    drive_file = session.exec(
        select(DriveFile).where(
            DriveFile.id == file_id,
            DriveFile.user_id == user_id,
            DriveFile.is_deleted == False,  # noqa: E712
        )
    ).first()
    if not drive_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    client_id, client_secret, _ = get_drive_credentials()
    access_token = await get_valid_access_token(session, user_id, client_id, client_secret)

    media_type = drive_file.mime_type or "application/octet-stream"
    filename = drive_file.name
    if media_type in GoogleDriveClient.EXPORT_MIME_MAP:
        media_type = "application/pdf"
        if not filename.lower().endswith(".pdf"):
            filename = f"{filename}.pdf"

    ascii_safe = re.sub(r'[\\\/\r\n"]', "_", filename)
    encoded_filename = urllib.parse.quote(filename, safe="")
    content_disposition = f"attachment; filename=\"{ascii_safe}\"; filename*=UTF-8''{encoded_filename}"

    async def _stream() -> AsyncGenerator[bytes, None]:
        try:
            async with GoogleDriveClient(access_token) as client:
                async for chunk in client.stream_download(drive_file.drive_file_id, mime_type=drive_file.mime_type):
                    yield chunk
        except (ConnectionError, TimeoutError, RuntimeError, ValueError, OSError) as e:
            logger.error("Failed to download file %s from Drive: %s", file_id, e)
            raise

    return StreamingResponse(
        _stream(),
        media_type=media_type,
        headers={"Content-Disposition": content_disposition},
    )


@router.patch("/files/{file_id}", response_model=DriveFileResponse)
async def rename_file(
    file_id: int,
    request: RenameFileRequest,
    user_id: int = Depends(require_user_id),
    session: Session = Depends(get_session),
) -> DriveFileResponse:
    """Rename a file in Google Drive."""
    drive_file = session.exec(
        select(DriveFile).where(
            DriveFile.id == file_id,
            DriveFile.user_id == user_id,
            DriveFile.is_deleted == False,  # noqa: E712
        )
    ).first()
    if not drive_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    client_id, client_secret, _ = get_drive_credentials()
    access_token = await get_valid_access_token(session, user_id, client_id, client_secret)

    try:
        async with GoogleDriveClient(access_token) as client:
            await client.rename_file(drive_file.drive_file_id, request.name)
    except (ConnectionError, TimeoutError, RuntimeError, ValueError, OSError) as e:
        logger.error("Failed to rename file %s: %s", file_id, e)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to rename file.")

    drive_file.name = request.name
    drive_file.update_timestamp()
    session.add(drive_file)
    session.commit()
    session.refresh(drive_file)

    return DriveFileResponse(
        id=drive_file.id,  # type: ignore[arg-type]
        drive_file_id=drive_file.drive_file_id,
        name=drive_file.name,
        mime_type=drive_file.mime_type,
        size=drive_file.size,
        modified_time=drive_file.modified_time,
        last_synced_at=drive_file.last_synced_at,
        rag_status=drive_file.rag_status,
        rag_error=drive_file.rag_error,
    )


@router.delete("/files/{file_id}")
def delete_file(
    file_id: int,
    user_id: int = Depends(require_user_id),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    """Soft-delete a file from Sparkth (does not delete from Drive)."""
    drive_file = session.exec(
        select(DriveFile).where(
            DriveFile.id == file_id,
            DriveFile.user_id == user_id,
            DriveFile.is_deleted == False,  # noqa: E712
        )
    ).first()
    if not drive_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    drive_file.soft_delete()
    session.add(drive_file)
    session.commit()

    return {"detail": "File removed from Sparkth successfully"}


@router.get("/browse", response_model=DriveBrowseResponse)
async def browse_drive(
    folder_id: str | None = Query(None, description="Drive folder ID to browse (root if omitted)"),
    page_token: str | None = Query(None, description="Pagination token"),
    user_id: int = Depends(require_user_id),
    session: Session = Depends(get_session),
) -> DriveBrowseResponse:
    """Browse Google Drive contents."""
    client_id, client_secret, _ = get_drive_credentials()
    access_token = await get_valid_access_token(session, user_id, client_id, client_secret)

    async with GoogleDriveClient(access_token) as client:
        result = await client.browse(folder_id=folder_id, page_token=page_token)

    items: list[DriveBrowseItem] = []
    for f in result.get("files", []):
        modified_time = None
        if f.get("modifiedTime"):
            modified_time = datetime.fromisoformat(f["modifiedTime"].replace("Z", "+00:00"))

        items.append(
            DriveBrowseItem(
                id=f["id"],
                name=f["name"],
                mime_type=f.get("mimeType", ""),
                is_folder=f.get("mimeType") == GoogleDriveClient.FOLDER_MIME_TYPE,
                modified_time=modified_time,
                size=int(f["size"]) if f.get("size") else None,
            )
        )

    return DriveBrowseResponse(
        items=items,
        next_page_token=result.get("nextPageToken"),
    )
