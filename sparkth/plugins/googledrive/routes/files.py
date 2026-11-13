"""Google Drive file endpoints."""

import re
import urllib.parse
from collections.abc import AsyncGenerator, Sequence
from datetime import datetime
from typing import cast

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.db import get_async_session
from sparkth.lib.log import get_logger
from sparkth.lib.permissions.scopes import USER
from sparkth.plugins.googledrive.client import GoogleDriveClient
from sparkth.plugins.googledrive.models import DriveFile, DriveFolder
from sparkth.plugins.googledrive.oauth import get_valid_access_token
from sparkth.plugins.googledrive.permissions import DRIVE_DELETE, DRIVE_READ
from sparkth.plugins.googledrive.routes.dependencies import (
    get_drive_file,
    get_drive_file_owner_id,
    get_drive_folder,
    get_drive_folder_owner_id,
    require_user_id,
)
from sparkth.plugins.googledrive.routes.route_utils import batch_fetch_documents, get_drive_credentials
from sparkth.plugins.googledrive.schemas import (
    DriveBrowseItem,
    DriveBrowseResponse,
    DriveFileResponse,
    FileRagStatusResponse,
    FolderRagStatusResponse,
    PaginatedResponse,
)
from sparkth.plugins.googledrive.utils import soft_delete_drive_file

router = APIRouter()
logger = get_logger(__name__)


@router.get(
    "/folders/{folder_id}/files",
    response_model=PaginatedResponse[DriveFileResponse],
    dependencies=[Depends(DRIVE_READ.require_for_object(USER, get_drive_folder_owner_id))],
)
async def list_files(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of items to return"),
    folder: DriveFolder = Depends(get_drive_folder),
    session: AsyncSession = Depends(get_async_session),
) -> PaginatedResponse[DriveFileResponse]:
    """List files in a synced folder with pagination."""
    base_query = select(DriveFile).where(
        DriveFile.folder_id == folder.id,
        DriveFile.is_deleted == False,  # noqa: E712
    )

    total = (await session.exec(select(func.count()).select_from(base_query.subquery()))).one()
    page_files: Sequence[DriveFile] = (await session.exec(base_query.offset(skip).limit(limit))).all()

    document_ids = [f.document_id for f in page_files if f.document_id is not None]
    docs = await batch_fetch_documents(session, document_ids)

    return PaginatedResponse(
        items=[
            DriveFileResponse(
                id=cast(int, f.id),
                drive_file_id=f.drive_file_id,
                document_id=f.document_id,
                name=f.name,
                mime_type=f.mime_type,
                size=f.size,
                modified_time=f.modified_time,
                last_synced_at=f.last_synced_at,
                rag_status=docs[f.document_id].status if f.document_id and f.document_id in docs else None,
                rag_error=docs[f.document_id].error if f.document_id and f.document_id in docs else None,
            )
            for f in page_files
        ],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/files/{file_id}",
    response_model=DriveFileResponse,
    dependencies=[Depends(DRIVE_READ.require_for_object(USER, get_drive_file_owner_id))],
)
async def get_file(
    drive_file: DriveFile = Depends(get_drive_file),
    session: AsyncSession = Depends(get_async_session),
) -> DriveFileResponse:
    """Get file metadata."""
    doc = None
    if drive_file.document_id is not None:
        docs = await batch_fetch_documents(session, [drive_file.document_id])
        doc = docs.get(drive_file.document_id)

    return DriveFileResponse(
        id=cast(int, drive_file.id),
        drive_file_id=drive_file.drive_file_id,
        document_id=drive_file.document_id,
        name=drive_file.name,
        mime_type=drive_file.mime_type,
        size=drive_file.size,
        modified_time=drive_file.modified_time,
        last_synced_at=drive_file.last_synced_at,
        rag_status=doc.status if doc else None,
        rag_error=doc.error if doc else None,
    )


@router.get(
    "/files/{file_id}/rag-status",
    response_model=FileRagStatusResponse,
    dependencies=[Depends(DRIVE_READ.require_for_object(USER, get_drive_file_owner_id))],
)
async def get_file_rag_status(
    drive_file: DriveFile = Depends(get_drive_file),
    session: AsyncSession = Depends(get_async_session),
) -> FileRagStatusResponse:
    """Get the RAG processing status for a single file."""
    doc = None
    if drive_file.document_id is not None:
        docs = await batch_fetch_documents(session, [drive_file.document_id])
        doc = docs.get(drive_file.document_id)

    return FileRagStatusResponse(
        file_id=cast(int, drive_file.id),
        name=drive_file.name,
        rag_status=doc.status if doc else None,
        rag_error=doc.error if doc else None,
    )


@router.get(
    "/folders/{folder_id}/rag-status",
    response_model=FolderRagStatusResponse,
    dependencies=[Depends(DRIVE_READ.require_for_object(USER, get_drive_folder_owner_id))],
)
async def get_folder_rag_status(
    folder: DriveFolder = Depends(get_drive_folder),
    session: AsyncSession = Depends(get_async_session),
) -> FolderRagStatusResponse:
    """Get the RAG processing status for all files in a folder."""
    files_result = await session.exec(
        select(DriveFile).where(
            DriveFile.folder_id == folder.id,
            DriveFile.is_deleted == False,  # noqa: E712
        )
    )
    files = files_result.all()

    folder_document_ids = [f.document_id for f in files if f.document_id is not None]
    folder_docs = await batch_fetch_documents(session, folder_document_ids)

    return FolderRagStatusResponse(
        folder_id=cast(int, folder.id),
        files=[
            FileRagStatusResponse(
                file_id=cast(int, f.id),
                name=f.name,
                rag_status=(
                    folder_docs[f.document_id].status if f.document_id and f.document_id in folder_docs else None
                ),
                rag_error=(
                    folder_docs[f.document_id].error if f.document_id and f.document_id in folder_docs else None
                ),
            )
            for f in files
        ],
    )


@router.get(
    "/files/{file_id}/download",
    dependencies=[Depends(DRIVE_READ.require_for_object(USER, get_drive_file_owner_id))],
)
async def download_file(
    drive_file: DriveFile = Depends(get_drive_file),
    session: AsyncSession = Depends(get_async_session),
) -> StreamingResponse:
    """Download a file from Google Drive, using the file owner's Google connection."""
    client_id, client_secret, _redirect_uri = get_drive_credentials()
    access_token = await get_valid_access_token(session, drive_file.user_id, client_id, client_secret)

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
            logger.error("Failed to download file %s from Drive: %s", drive_file.id, e)
            raise

    return StreamingResponse(
        _stream(),
        media_type=media_type,
        headers={"Content-Disposition": content_disposition},
    )


@router.delete(
    "/files/{file_id}",
    dependencies=[Depends(DRIVE_DELETE.require_for_object(USER, get_drive_file_owner_id))],
)
async def delete_file(
    drive_file: DriveFile = Depends(get_drive_file),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, str]:
    """Soft-delete a file from Sparkth (does not delete from Drive)."""
    await soft_delete_drive_file(session, drive_file)
    await session.commit()

    return {"detail": "File removed from Sparkth successfully"}


@router.get("/browse", response_model=DriveBrowseResponse)
async def browse_drive(
    folder_id: str | None = Query(None, description="Drive folder ID to browse (root if omitted)"),
    page_token: str | None = Query(None, description="Pagination token"),
    user_id: int = Depends(require_user_id),
    session: AsyncSession = Depends(get_async_session),
) -> DriveBrowseResponse:
    """Browse Google Drive contents."""
    client_id, client_secret, _redirect_uri = get_drive_credentials()
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
