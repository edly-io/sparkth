"""Google Drive API Endpoints."""

import logging
import re
import urllib.parse
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy import func
from sqlmodel import Session, select

from app.api.v1.auth import get_current_user
from app.core.config import get_settings
from app.core.db import get_session
from app.core_plugins.googledrive.client import GoogleDriveClient
from app.core_plugins.googledrive.oauth import (
    decode_state,
    decrypt_token,
    delete_token,
    exchange_code_for_tokens,
    generate_authorization_url,
    get_token_record,
    get_user_info,
    get_valid_access_token,
    revoke_token,
    save_tokens,
)
from app.core_plugins.googledrive.types import (
    AuthorizationUrlResponse,
    ConnectionStatusResponse,
    CreateFolderRequest,
    DriveBrowseItem,
    DriveBrowseResponse,
    DriveFileResponse,
    DriveFolderResponse,
    DriveFolderWithFilesResponse,
    RenameFileRequest,
    SyncFolderRequest,
    SyncStatusResponse,
)
from app.core_plugins.googledrive.utils import process_folder_rag
from app.models.drive import DriveFile, DriveFolder
from app.models.user import User

router: APIRouter = APIRouter()
logger = logging.getLogger(__name__)


def require_user_id(current_user: User = Depends(get_current_user)) -> int:
    """Dependency that extracts and validates the current user's ID."""
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not authenticated")
    return current_user.id


def get_drive_credentials() -> tuple[str, str, str]:
    """Get Google OAuth credentials from app settings.

    Returns:
        Tuple of (client_id, client_secret, redirect_uri)

    Raises:
        HTTPException: If credentials are not configured
    """
    settings = get_settings()
    client_id = settings.GOOGLE_CLIENT_ID
    client_secret = settings.GOOGLE_CLIENT_SECRET
    redirect_uri = settings.GOOGLE_DRIVE_REDIRECT_URI

    if not client_id or not client_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google Drive credentials not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.",
        )

    return client_id, client_secret, redirect_uri


async def _sync_folder_files(session: Session, folder: DriveFolder, user_id: int, access_token: str) -> int:
    """Fetch files from Drive and sync them to the database.

    Returns:
        Number of active (non-deleted) files after sync.
    """
    async with GoogleDriveClient(access_token) as client:
        drive_files_data = await client.list_files(folder_id=folder.drive_folder_id)

    now = datetime.now(timezone.utc)
    drive_files = drive_files_data.get("files", [])
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
                folder_id=folder.id,  # type: ignore[arg-type]
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
    session.commit()
    session.refresh(folder)

    return len(drive_files)


# ---------------------------------------------------------------------------
# OAuth Endpoints
# ---------------------------------------------------------------------------


@router.get("/oauth/authorize", response_model=AuthorizationUrlResponse)
def get_authorization_url(
    current_user: User = Depends(get_current_user),
    user_id: int = Depends(require_user_id),
    session: Session = Depends(get_session),
) -> AuthorizationUrlResponse:
    """Generate Google OAuth authorization URL."""
    client_id, _, redirect_uri = get_drive_credentials()
    url = generate_authorization_url(user_id, client_id, redirect_uri, login_hint=current_user.email)
    return AuthorizationUrlResponse(url=url)


@router.get("/oauth/callback")
async def oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Handle OAuth callback from Google.

    The state parameter is a signed, time-limited token containing the user_id.
    This provides CSRF protection (signature) and replay protection (expiry).
    """
    from itsdangerous import BadSignature, SignatureExpired

    try:
        state_data = decode_state(state)
        user_id = state_data["user_id"]
    except SignatureExpired:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth state expired. Please try again.")
    except BadSignature, KeyError, ValueError, TypeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state.")

    client_id, client_secret, redirect_uri = get_drive_credentials()

    try:
        token_data = await exchange_code_for_tokens(code, client_id, client_secret, redirect_uri)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to exchange authorization code.")

    # Only save refresh_token if Google returned one; otherwise keep the existing one
    refresh_token = token_data.get("refresh_token", "")
    if not refresh_token:
        existing = get_token_record(session, user_id)
        if existing:
            refresh_token = decrypt_token(existing.refresh_token_encrypted)

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No refresh token received. Please disconnect and reconnect Google Drive.",
        )

    try:
        save_tokens(
            session,
            user_id,
            token_data["access_token"],
            refresh_token,
            token_data["expires_in"],
            token_data.get("scope", ""),
        )
    except KeyError, ValueError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save tokens.",
        )

    return RedirectResponse(url="/dashboard/google-drive?connected=true")


@router.delete("/oauth/disconnect")
async def disconnect_drive(
    user_id: int = Depends(require_user_id),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    """Disconnect Google Drive by revoking and deleting tokens."""
    token_record = get_token_record(session, user_id)
    if not token_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Google Drive not connected")

    # Try to revoke the token with Google
    try:
        access_token = decrypt_token(token_record.access_token_encrypted)
        await revoke_token(access_token)
    except ValueError:
        logger.warning("Failed to decrypt token for revocation, proceeding with deletion")

    delete_token(session, user_id)
    return {"detail": "Google Drive disconnected successfully"}


@router.get("/oauth/status", response_model=ConnectionStatusResponse)
async def get_connection_status(
    user_id: int = Depends(require_user_id),
    session: Session = Depends(get_session),
) -> ConnectionStatusResponse:
    """Get Google Drive connection status."""
    token_record = get_token_record(session, user_id)
    if not token_record:
        return ConnectionStatusResponse(connected=False)

    try:
        client_id, client_secret, _ = get_drive_credentials()
        access_token = await get_valid_access_token(session, user_id, client_id, client_secret)
        user_info = await get_user_info(access_token)
        return ConnectionStatusResponse(
            connected=True,
            email=user_info.get("email"),
            expires_at=token_record.token_expiry,
        )
    except ValueError, HTTPException:
        return ConnectionStatusResponse(connected=False)


# ---------------------------------------------------------------------------
# Folder Endpoints
# ---------------------------------------------------------------------------


@router.get("/folders", response_model=list[DriveFolderResponse])
def list_folders(
    user_id: int = Depends(require_user_id),
    session: Session = Depends(get_session),
) -> list[DriveFolderResponse]:
    """List all synced Google Drive folders for the current user."""
    # Single query with file count to avoid N+1
    file_count_subq = (
        select(DriveFile.folder_id, func.count(DriveFile.id).label("file_count"))  # type: ignore[arg-type]
        .where(DriveFile.is_deleted == False)  # noqa: E712
        .group_by(DriveFile.folder_id)  # type: ignore[arg-type]
        .subquery()
    )

    stmt = (
        select(DriveFolder, file_count_subq.c.file_count)
        .outerjoin(file_count_subq, DriveFolder.id == file_count_subq.c.folder_id)  # type: ignore[arg-type]
        .where(
            DriveFolder.user_id == user_id,
            DriveFolder.is_deleted == False,  # noqa: E712
        )
    )
    rows = session.exec(stmt).all()

    return [
        DriveFolderResponse(
            id=folder.id,  # type: ignore[arg-type]
            drive_folder_id=folder.drive_folder_id,
            name=folder.drive_folder_name,
            parent_id=folder.drive_parent_id,
            file_count=file_count or 0,
            last_synced_at=folder.last_synced_at,
            sync_status=folder.sync_status,
        )
        for folder, file_count in rows
    ]


@router.post("/folders/sync", response_model=DriveFolderResponse)
async def sync_folder(
    request: SyncFolderRequest,
    user_id: int = Depends(require_user_id),
    session: Session = Depends(get_session),
) -> DriveFolderResponse:
    """Sync an existing Google Drive folder."""
    client_id, client_secret, _ = get_drive_credentials()
    access_token = await get_valid_access_token(session, user_id, client_id, client_secret)

    # Check if folder is already synced
    existing = session.exec(
        select(DriveFolder).where(
            DriveFolder.user_id == user_id,
            DriveFolder.drive_folder_id == request.drive_folder_id,
            DriveFolder.is_deleted == False,  # noqa: E712
        )
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Folder is already synced")

    # Get folder metadata from Drive
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
    session.commit()
    session.refresh(folder)

    # Fetch files immediately so the folder isn't empty
    file_count = await _sync_folder_files(session, folder, user_id, access_token)

    # Trigger RAG pipeline for all supported files in the folder
    await process_folder_rag(folder, user_id, access_token, session)

    return DriveFolderResponse(
        id=folder.id,  # type: ignore[arg-type]
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
    session: Session = Depends(get_session),
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
    session.commit()
    session.refresh(folder)

    return DriveFolderResponse(
        id=folder.id,  # type: ignore[arg-type]
        drive_folder_id=folder.drive_folder_id,
        name=folder.drive_folder_name,
        parent_id=folder.drive_parent_id,
        file_count=0,
        last_synced_at=folder.last_synced_at,
        sync_status=folder.sync_status,
    )


@router.get("/folders/{folder_id}", response_model=DriveFolderWithFilesResponse)
def get_folder(
    folder_id: int,
    user_id: int = Depends(require_user_id),
    session: Session = Depends(get_session),
) -> DriveFolderWithFilesResponse:
    """Get a synced folder with its files."""
    folder = session.exec(
        select(DriveFolder).where(
            DriveFolder.id == folder_id,
            DriveFolder.user_id == user_id,
            DriveFolder.is_deleted == False,  # noqa: E712
        )
    ).first()
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")

    folder_files = session.exec(
        select(DriveFile).where(
            DriveFile.folder_id == folder.id,
            DriveFile.is_deleted == False,  # noqa: E712
        )
    ).all()

    files = [
        DriveFileResponse(
            id=f.id,  # type: ignore[arg-type]
            drive_file_id=f.drive_file_id,
            name=f.name,
            mime_type=f.mime_type,
            size=f.size,
            modified_time=f.modified_time,
            last_synced_at=f.last_synced_at,
        )
        for f in folder_files
    ]

    return DriveFolderWithFilesResponse(
        id=folder.id,  # type: ignore[arg-type]
        drive_folder_id=folder.drive_folder_id,
        name=folder.drive_folder_name,
        parent_id=folder.drive_parent_id,
        file_count=len(files),
        last_synced_at=folder.last_synced_at,
        sync_status=folder.sync_status,
        files=files,
    )


@router.delete("/folders/{folder_id}")
def delete_folder(
    folder_id: int,
    user_id: int = Depends(require_user_id),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    """Soft delete a synced folder and its files from Sparkth (does not delete from Drive)."""
    folder = session.exec(
        select(DriveFolder).where(
            DriveFolder.id == folder_id,
            DriveFolder.user_id == user_id,
            DriveFolder.is_deleted == False,  # noqa: E712
        )
    ).first()
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")

    # Soft delete all files in the folder
    folder_files = session.exec(
        select(DriveFile).where(
            DriveFile.folder_id == folder.id,
            DriveFile.is_deleted == False,  # noqa: E712
        )
    ).all()
    for f in folder_files:
        f.soft_delete()
        session.add(f)

    folder.soft_delete()
    session.add(folder)
    session.commit()

    return {"detail": "Folder removed from Sparkth successfully"}


@router.post("/folders/{folder_id}/refresh", response_model=SyncStatusResponse)
async def refresh_folder(
    folder_id: int,
    user_id: int = Depends(require_user_id),
    session: Session = Depends(get_session),
) -> SyncStatusResponse:
    """Refresh folder contents from Google Drive."""
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

    try:
        await _sync_folder_files(session, folder, user_id, access_token)

        # Trigger RAG pipeline for all supported files in the folder
        await process_folder_rag(folder, user_id, access_token, session)

        return SyncStatusResponse(
            folder_id=folder.id,  # type: ignore[arg-type]
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
        session.commit()
        session.refresh(folder)

        return SyncStatusResponse(
            folder_id=folder.id,  # type: ignore[arg-type]
            sync_status="error",
            last_synced_at=folder.last_synced_at,
            error=str(e),
        )


# ---------------------------------------------------------------------------
# File Endpoints
# ---------------------------------------------------------------------------


@router.get("/folders/{folder_id}/files", response_model=list[DriveFileResponse])
def list_files(
    folder_id: int,
    user_id: int = Depends(require_user_id),
    session: Session = Depends(get_session),
) -> list[DriveFileResponse]:
    """List files in a synced folder."""
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

    return [
        DriveFileResponse(
            id=f.id,  # type: ignore[arg-type]
            drive_file_id=f.drive_file_id,
            name=f.name,
            mime_type=f.mime_type,
            size=f.size,
            modified_time=f.modified_time,
            last_synced_at=f.last_synced_at,
        )
        for f in files
    ]


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
    if len(content) > 30 * 1024 * 1024:
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

    # Google Docs native types are exported as PDF
    media_type = drive_file.mime_type or "application/octet-stream"
    filename = drive_file.name
    if media_type in GoogleDriveClient.EXPORT_MIME_MAP:
        media_type = "application/pdf"
        if not filename.lower().endswith(".pdf"):
            filename = f"{filename}.pdf"

    # Sanitize filename for Content-Disposition header
    ascii_safe = re.sub(r'[\\\/\r\n"]', "_", filename)
    # RFC 5987 filename* for non-ASCII filenames
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
    )


@router.delete("/files/{file_id}")
async def delete_file(
    file_id: int,
    user_id: int = Depends(require_user_id),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    """Delete a file from Google Drive and soft-delete locally."""
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
            await client.delete_file(drive_file.drive_file_id)
    except (ConnectionError, TimeoutError, RuntimeError, ValueError, OSError) as e:
        logger.error("Failed to delete file %s: %s", file_id, e)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to delete file.")

    drive_file.soft_delete()
    session.add(drive_file)
    session.commit()

    return {"detail": "File deleted successfully"}


# ---------------------------------------------------------------------------
# Browse Endpoint
# ---------------------------------------------------------------------------


@router.get("/browse", response_model=DriveBrowseResponse)
async def browse_drive(
    folder_id: Optional[str] = Query(None, description="Drive folder ID to browse (root if omitted)"),
    page_token: Optional[str] = Query(None, description="Pagination token"),
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
