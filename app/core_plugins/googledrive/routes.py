"""Google Drive API Endpoints."""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlmodel import Session, select

from app.api.v1.auth import get_current_user
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
from app.models.drive import DriveFile, DriveFolder
from app.models.plugin import Plugin, UserPlugin
from app.models.user import User

router: APIRouter = APIRouter()
logger = logging.getLogger(__name__)


def get_drive_credentials(session: Session, user_id: int) -> tuple[str, str, str]:
    """Get Google OAuth credentials from plugin config.

    Returns:
        Tuple of (client_id, client_secret, redirect_uri)

    Raises:
        HTTPException: If credentials are not configured
    """
    # Try user-level config first
    user_plugin = session.exec(
        select(UserPlugin).where(
            UserPlugin.user_id == user_id,
            UserPlugin.plugin_id == select(Plugin.id).where(Plugin.name == "google-drive").scalar_subquery(),
        )
    ).first()

    config: dict[str, Any] = {}
    if user_plugin and user_plugin.config:
        config = user_plugin.config

    # Fall back to plugin-level defaults
    if not config.get("google_client_id"):
        plugin = session.exec(
            select(Plugin).where(Plugin.name == "google-drive")
        ).first()
        if plugin and plugin.config_schema:
            # config_schema stores the schema definition, not actual values
            # For system-wide credentials, check environment as ultimate fallback
            config.setdefault("google_client_id", os.environ.get("GOOGLE_CLIENT_ID", ""))
            config.setdefault("google_client_secret", os.environ.get("GOOGLE_CLIENT_SECRET", ""))
            config.setdefault(
                "google_redirect_uri",
                os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/v1/googledrive/oauth/callback"),
            )

    client_id = config.get("google_client_id", "")
    client_secret = config.get("google_client_secret", "")
    redirect_uri = config.get(
        "google_redirect_uri", "http://localhost:8000/api/v1/googledrive/oauth/callback"
    )

    if not client_id or not client_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google Drive credentials not configured. Please configure the Google Drive plugin.",
        )

    return client_id, client_secret, redirect_uri


# ---------------------------------------------------------------------------
# OAuth Endpoints
# ---------------------------------------------------------------------------


@router.get("/oauth/authorize", response_model=AuthorizationUrlResponse)
def get_authorization_url(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> AuthorizationUrlResponse:
    """Generate Google OAuth authorization URL."""
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not authenticated")
    client_id, _, redirect_uri = get_drive_credentials(session, current_user.id)
    url = generate_authorization_url(current_user.id, client_id, redirect_uri)
    return AuthorizationUrlResponse(url=url)


@router.get("/oauth/callback")
async def oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Handle OAuth callback from Google."""
    try:
        state_data = decode_state(state)
        user_id = state_data["user_id"]
    except (KeyError, ValueError, TypeError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid state parameter: {e}")

    client_id, client_secret, redirect_uri = get_drive_credentials(session, user_id)

    try:
        token_data = await exchange_code_for_tokens(code, client_id, client_secret, redirect_uri)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to exchange code for tokens: {e}")

    try:
        save_tokens(
            session,
            user_id,
            token_data["access_token"],
            token_data.get("refresh_token", ""),
            token_data["expires_in"],
            token_data.get("scope", ""),
        )
    except (KeyError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save tokens: {e}",
        )

    return RedirectResponse(url="/dashboard/google-drive?connected=true")


@router.delete("/oauth/disconnect")
async def disconnect_drive(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    """Disconnect Google Drive by revoking and deleting tokens."""
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not authenticated")

    token_record = get_token_record(session, current_user.id)
    if not token_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Google Drive not connected")

    # Try to revoke the token with Google
    try:
        access_token = decrypt_token(token_record.access_token_encrypted)
        await revoke_token(access_token)
    except ValueError:
        logger.warning("Failed to decrypt token for revocation, proceeding with deletion")

    delete_token(session, current_user.id)
    return {"detail": "Google Drive disconnected successfully"}


@router.get("/oauth/status", response_model=ConnectionStatusResponse)
async def get_connection_status(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ConnectionStatusResponse:
    """Get Google Drive connection status."""
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not authenticated")

    token_record = get_token_record(session, current_user.id)
    if not token_record:
        return ConnectionStatusResponse(connected=False)

    try:
        client_id, client_secret, _ = get_drive_credentials(session, current_user.id)
        access_token = await get_valid_access_token(session, current_user.id, client_id, client_secret)
        user_info = await get_user_info(access_token)
        return ConnectionStatusResponse(
            connected=True,
            email=user_info.get("email"),
            expires_at=token_record.token_expiry,
        )
    except (ValueError, HTTPException):
        return ConnectionStatusResponse(connected=False)


# ---------------------------------------------------------------------------
# Folder Endpoints
# ---------------------------------------------------------------------------


@router.get("/folders", response_model=list[DriveFolderResponse])
def list_folders(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[DriveFolderResponse]:
    """List all synced Google Drive folders for the current user."""
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not authenticated")

    folders = session.exec(
        select(DriveFolder).where(
            DriveFolder.user_id == current_user.id,
            DriveFolder.is_deleted == False,  # noqa: E712
        )
    ).all()

    result: list[DriveFolderResponse] = []
    for folder in folders:
        file_count = len([f for f in folder.files if not f.is_deleted])
        result.append(
            DriveFolderResponse(
                id=folder.id,  # type: ignore[arg-type]
                drive_folder_id=folder.drive_folder_id,
                name=folder.drive_folder_name,
                parent_id=folder.drive_parent_id,
                file_count=file_count,
                last_synced_at=folder.last_synced_at,
                sync_status=folder.sync_status,
            )
        )
    return result


@router.post("/folders/sync", response_model=DriveFolderResponse)
async def sync_folder(
    request: SyncFolderRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> DriveFolderResponse:
    """Sync an existing Google Drive folder."""
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not authenticated")

    client_id, client_secret, _ = get_drive_credentials(session, current_user.id)
    access_token = await get_valid_access_token(session, current_user.id, client_id, client_secret)

    # Check if folder is already synced
    existing = session.exec(
        select(DriveFolder).where(
            DriveFolder.user_id == current_user.id,
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
        user_id=current_user.id,
        drive_folder_id=folder_metadata["id"],
        drive_folder_name=folder_metadata["name"],
        drive_parent_id=folder_metadata.get("parents", [None])[0] if folder_metadata.get("parents") else None,
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


@router.post("/folders", response_model=DriveFolderResponse)
async def create_folder(
    request: CreateFolderRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> DriveFolderResponse:
    """Create a new folder in Google Drive and sync it."""
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not authenticated")

    client_id, client_secret, _ = get_drive_credentials(session, current_user.id)
    access_token = await get_valid_access_token(session, current_user.id, client_id, client_secret)

    async with GoogleDriveClient(access_token) as client:
        folder_metadata = await client.create_folder(request.name, request.parent_id)

    now = datetime.now(timezone.utc)
    folder = DriveFolder(
        user_id=current_user.id,
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
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> DriveFolderWithFilesResponse:
    """Get a synced folder with its files."""
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not authenticated")

    folder = session.exec(
        select(DriveFolder).where(
            DriveFolder.id == folder_id,
            DriveFolder.user_id == current_user.id,
            DriveFolder.is_deleted == False,  # noqa: E712
        )
    ).first()
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")

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
        for f in folder.files
        if not f.is_deleted
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
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    """Soft delete a synced folder and its files from Sparkth (does not delete from Drive)."""
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not authenticated")

    folder = session.exec(
        select(DriveFolder).where(
            DriveFolder.id == folder_id,
            DriveFolder.user_id == current_user.id,
            DriveFolder.is_deleted == False,  # noqa: E712
        )
    ).first()
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")

    # Soft delete all files in the folder
    for f in folder.files:
        if not f.is_deleted:
            f.soft_delete()
            session.add(f)

    folder.soft_delete()
    session.add(folder)
    session.commit()

    return {"detail": "Folder removed from Sparkth successfully"}


@router.post("/folders/{folder_id}/refresh", response_model=SyncStatusResponse)
async def refresh_folder(
    folder_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> SyncStatusResponse:
    """Refresh folder contents from Google Drive."""
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not authenticated")

    folder = session.exec(
        select(DriveFolder).where(
            DriveFolder.id == folder_id,
            DriveFolder.user_id == current_user.id,
            DriveFolder.is_deleted == False,  # noqa: E712
        )
    ).first()
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")

    client_id, client_secret, _ = get_drive_credentials(session, current_user.id)
    access_token = await get_valid_access_token(session, current_user.id, client_id, client_secret)

    try:
        async with GoogleDriveClient(access_token) as client:
            drive_files_data = await client.list_files(folder_id=folder.drive_folder_id)

        now = datetime.now(timezone.utc)
        drive_files = drive_files_data.get("files", [])
        drive_file_ids = {f["id"] for f in drive_files}

        # Get existing files for this folder
        existing_files = session.exec(
            select(DriveFile).where(
                DriveFile.folder_id == folder.id,
                DriveFile.is_deleted == False,  # noqa: E712
            )
        ).all()
        existing_map = {f.drive_file_id: f for f in existing_files}

        # Update or create files
        for df in drive_files:
            modified_time = None
            if df.get("modifiedTime"):
                modified_time = datetime.fromisoformat(df["modifiedTime"].replace("Z", "+00:00"))

            if df["id"] in existing_map:
                # Update existing file
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
                # Create new file record
                new_file = DriveFile(
                    folder_id=folder.id,  # type: ignore[arg-type]
                    user_id=current_user.id,
                    drive_file_id=df["id"],
                    name=df["name"],
                    mime_type=df.get("mimeType"),
                    size=int(df["size"]) if df.get("size") else None,
                    md5_checksum=df.get("md5Checksum"),
                    modified_time=modified_time,
                    last_synced_at=now,
                )
                session.add(new_file)

        # Soft delete files no longer in Drive
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

        return SyncStatusResponse(
            folder_id=folder.id,  # type: ignore[arg-type]
            sync_status=folder.sync_status,
            last_synced_at=folder.last_synced_at,
        )

    except HTTPException:
        raise
    except (ConnectionError, TimeoutError, ValueError) as e:
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
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[DriveFileResponse]:
    """List files in a synced folder."""
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not authenticated")

    folder = session.exec(
        select(DriveFolder).where(
            DriveFolder.id == folder_id,
            DriveFolder.user_id == current_user.id,
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
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> DriveFileResponse:
    """Upload a file to a Google Drive folder."""
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not authenticated")

    folder = session.exec(
        select(DriveFolder).where(
            DriveFolder.id == folder_id,
            DriveFolder.user_id == current_user.id,
            DriveFolder.is_deleted == False,  # noqa: E712
        )
    ).first()
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")

    client_id, client_secret, _ = get_drive_credentials(session, current_user.id)
    access_token = await get_valid_access_token(session, current_user.id, client_id, client_secret)

    content = await file.read()
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
        user_id=current_user.id,
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
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> DriveFileResponse:
    """Get file metadata."""
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not authenticated")

    drive_file = session.exec(
        select(DriveFile).where(
            DriveFile.id == file_id,
            DriveFile.user_id == current_user.id,
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
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> StreamingResponse:
    """Download a file from Google Drive."""
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not authenticated")

    drive_file = session.exec(
        select(DriveFile).where(
            DriveFile.id == file_id,
            DriveFile.user_id == current_user.id,
            DriveFile.is_deleted == False,  # noqa: E712
        )
    ).first()
    if not drive_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    client_id, client_secret, _ = get_drive_credentials(session, current_user.id)
    access_token = await get_valid_access_token(session, current_user.id, client_id, client_secret)

    async with GoogleDriveClient(access_token) as client:
        content = await client.download_file(drive_file.drive_file_id)

    return StreamingResponse(
        iter([content]),
        media_type=drive_file.mime_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{drive_file.name}"',
        },
    )


@router.patch("/files/{file_id}", response_model=DriveFileResponse)
async def rename_file(
    file_id: int,
    request: RenameFileRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> DriveFileResponse:
    """Rename a file in Google Drive."""
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not authenticated")

    drive_file = session.exec(
        select(DriveFile).where(
            DriveFile.id == file_id,
            DriveFile.user_id == current_user.id,
            DriveFile.is_deleted == False,  # noqa: E712
        )
    ).first()
    if not drive_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    client_id, client_secret, _ = get_drive_credentials(session, current_user.id)
    access_token = await get_valid_access_token(session, current_user.id, client_id, client_secret)

    async with GoogleDriveClient(access_token) as client:
        await client.rename_file(drive_file.drive_file_id, request.name)

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
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    """Delete a file from Google Drive and soft-delete locally."""
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not authenticated")

    drive_file = session.exec(
        select(DriveFile).where(
            DriveFile.id == file_id,
            DriveFile.user_id == current_user.id,
            DriveFile.is_deleted == False,  # noqa: E712
        )
    ).first()
    if not drive_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    client_id, client_secret, _ = get_drive_credentials(session, current_user.id)
    access_token = await get_valid_access_token(session, current_user.id, client_id, client_secret)

    async with GoogleDriveClient(access_token) as client:
        await client.delete_file(drive_file.drive_file_id)

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
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> DriveBrowseResponse:
    """Browse Google Drive contents."""
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not authenticated")

    client_id, client_secret, _ = get_drive_credentials(session, current_user.id)
    access_token = await get_valid_access_token(session, current_user.id, client_id, client_secret)

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
