"""
Google Drive API Endpoints

Provides OAuth authentication, folder management, and file operations for Google Drive.
"""

from datetime import datetime, timezone
from typing import Any, List, Optional

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
from app.models.user import User

router: APIRouter = APIRouter()


# OAuth Endpoints
@router.get("/oauth/authorize", response_model=AuthorizationUrlResponse)
def get_authorization_url(
    current_user: User = Depends(get_current_user),
) -> AuthorizationUrlResponse:
    """Generate Google OAuth authorization URL."""
    if current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated",
        )
    url = generate_authorization_url(current_user.id)
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
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid state parameter: {e}",
        )

    try:
        token_data = await exchange_code_for_tokens(code)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to exchange code for tokens: {e}",
        )

    save_tokens(
        session,
        user_id,
        token_data["access_token"],
        token_data.get("refresh_token", ""),
        token_data["expires_in"],
        token_data.get("scope", ""),
    )

    # Redirect back to frontend
    return RedirectResponse(url="/drive?connected=true")


@router.delete("/oauth/disconnect")
async def disconnect_google(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Revoke tokens and disconnect Google account."""
    if current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated",
        )

    token_record = get_token_record(session, current_user.id)
    if token_record:
        # Revoke tokens on Google side
        try:
            access_token = decrypt_token(token_record.access_token_encrypted)
            await revoke_token(access_token)
        except Exception:
            pass  # Continue even if revocation fails

        delete_token(session, current_user.id)

    return {"message": "Disconnected from Google Drive"}


@router.get("/oauth/status", response_model=ConnectionStatusResponse)
async def get_connection_status(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ConnectionStatusResponse:
    """Check if user has valid Google connection."""
    if current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated",
        )

    token_record = get_token_record(session, current_user.id)
    if not token_record:
        return ConnectionStatusResponse(connected=False)

    # Try to get user info to verify connection
    try:
        access_token = await get_valid_access_token(session, current_user.id)
        user_info = await get_user_info(access_token)
        return ConnectionStatusResponse(
            connected=True,
            email=user_info.get("email"),
            expires_at=token_record.token_expiry,
        )
    except Exception:
        return ConnectionStatusResponse(connected=False)


# Folder Endpoints
@router.get("/folders", response_model=List[DriveFolderResponse])
def list_synced_folders(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> List[DriveFolderResponse]:
    """List all synced folders for the current user."""
    if current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated",
        )

    statement = select(DriveFolder).where(
        DriveFolder.user_id == current_user.id,
        DriveFolder.is_deleted == False,
    )
    folders = session.exec(statement).all()

    result = []
    for folder in folders:
        # Count files in folder
        file_count_stmt = select(DriveFile).where(
            DriveFile.folder_id == folder.id,
            DriveFile.is_deleted == False,
        )
        file_count = len(session.exec(file_count_stmt).all())

        if folder.id is None:
            continue
        result.append(
            DriveFolderResponse(
                id=folder.id,
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
async def sync_drive_folder(
    request: SyncFolderRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> DriveFolderResponse:
    """Sync a Google Drive folder (add to Sparkth)."""
    if current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated",
        )

    # Check if folder already synced
    existing = session.exec(
        select(DriveFolder).where(
            DriveFolder.user_id == current_user.id,
            DriveFolder.drive_folder_id == request.drive_folder_id,
            DriveFolder.is_deleted == False,
        )
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Folder already synced",
        )

    # Get folder info from Google Drive
    try:
        access_token = await get_valid_access_token(session, current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    async with GoogleDriveClient(access_token) as client:
        try:
            folder_info = await client.get_folder(request.drive_folder_id)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to get folder from Google Drive: {e}",
            )

    # Create folder record
    folder = DriveFolder(
        user_id=current_user.id,
        drive_folder_id=request.drive_folder_id,
        drive_folder_name=folder_info.get("name", "Untitled"),
        drive_parent_id=folder_info.get("parents", [None])[0] if folder_info.get("parents") else None,
        sync_status="pending",
    )
    session.add(folder)
    session.commit()
    session.refresh(folder)

    if folder.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create folder record",
        )
    return DriveFolderResponse(
        id=folder.id,
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated",
        )

    try:
        access_token = await get_valid_access_token(session, current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    async with GoogleDriveClient(access_token) as client:
        try:
            folder_info = await client.create_folder(request.name, request.parent_id)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to create folder in Google Drive: {e}",
            )

    # Create folder record
    folder = DriveFolder(
        user_id=current_user.id,
        drive_folder_id=folder_info["id"],
        drive_folder_name=folder_info["name"],
        drive_parent_id=request.parent_id,
        sync_status="synced",
        last_synced_at=datetime.now(timezone.utc),
    )
    session.add(folder)
    session.commit()
    session.refresh(folder)

    if folder.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create folder record",
        )
    return DriveFolderResponse(
        id=folder.id,
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
    """Get folder with its files."""
    if current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated",
        )

    folder = session.exec(
        select(DriveFolder).where(
            DriveFolder.id == folder_id,
            DriveFolder.user_id == current_user.id,
            DriveFolder.is_deleted == False,
        )
    ).first()

    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found",
        )

    # Get files
    files = session.exec(
        select(DriveFile).where(
            DriveFile.folder_id == folder_id,
            DriveFile.is_deleted == False,
        )
    ).all()

    return DriveFolderWithFilesResponse(
        id=folder_id,
        drive_folder_id=folder.drive_folder_id,
        name=folder.drive_folder_name,
        parent_id=folder.drive_parent_id,
        file_count=len(files),
        last_synced_at=folder.last_synced_at,
        sync_status=folder.sync_status,
        files=[
            DriveFileResponse(
                id=f.id,
                drive_file_id=f.drive_file_id,
                name=f.name,
                mime_type=f.mime_type,
                size=f.size,
                modified_time=f.modified_time,
                last_synced_at=f.last_synced_at,
            )
            for f in files
            if f.id is not None
        ],
    )


@router.delete("/folders/{folder_id}")
def remove_folder(
    folder_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Remove folder from Sparkth (doesn't delete from Drive)."""
    if current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated",
        )

    folder = session.exec(
        select(DriveFolder).where(
            DriveFolder.id == folder_id,
            DriveFolder.user_id == current_user.id,
            DriveFolder.is_deleted == False,
        )
    ).first()

    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found",
        )

    # Soft delete folder and its files
    folder.soft_delete()
    session.add(folder)

    files = session.exec(
        select(DriveFile).where(
            DriveFile.folder_id == folder_id,
            DriveFile.is_deleted == False,
        )
    ).all()

    for file in files:
        file.soft_delete()
        session.add(file)

    session.commit()

    return {"message": "Folder removed from Sparkth"}


@router.post("/folders/{folder_id}/refresh", response_model=SyncStatusResponse)
async def refresh_folder(
    folder_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> SyncStatusResponse:
    """Manual sync - refresh metadata from Google Drive."""
    if current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated",
        )

    folder = session.exec(
        select(DriveFolder).where(
            DriveFolder.id == folder_id,
            DriveFolder.user_id == current_user.id,
            DriveFolder.is_deleted == False,
        )
    ).first()

    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found",
        )

    # Update sync status
    folder.sync_status = "syncing"
    session.add(folder)
    session.commit()

    try:
        access_token = await get_valid_access_token(session, current_user.id)
    except ValueError as e:
        folder.sync_status = "error"
        folder.sync_error = str(e)
        session.add(folder)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    try:
        async with GoogleDriveClient(access_token) as client:
            # Get files from Google Drive
            result = await client.list_files(folder_id=folder.drive_folder_id)
            drive_files = result.get("files", [])

            # Get existing file records
            existing_files = session.exec(
                select(DriveFile).where(
                    DriveFile.folder_id == folder_id,
                    DriveFile.is_deleted == False,
                )
            ).all()
            existing_by_drive_id = {f.drive_file_id: f for f in existing_files}

            # Track seen drive IDs
            seen_drive_ids = set()

            for df in drive_files:
                drive_file_id = df["id"]
                seen_drive_ids.add(drive_file_id)

                # Parse modified time
                modified_time = None
                if df.get("modifiedTime"):
                    try:
                        modified_time = datetime.fromisoformat(df["modifiedTime"].replace("Z", "+00:00"))
                    except Exception:
                        pass

                if drive_file_id in existing_by_drive_id:
                    # Update existing file
                    file = existing_by_drive_id[drive_file_id]
                    file.name = df["name"]
                    file.mime_type = df.get("mimeType")
                    file.size = int(df["size"]) if df.get("size") else None
                    file.md5_checksum = df.get("md5Checksum")
                    file.modified_time = modified_time
                    file.last_synced_at = datetime.now(timezone.utc)
                    file.update_timestamp()
                    session.add(file)
                else:
                    # Create new file record
                    file = DriveFile(
                        folder_id=folder_id,
                        user_id=current_user.id,
                        drive_file_id=drive_file_id,
                        name=df["name"],
                        mime_type=df.get("mimeType"),
                        size=int(df["size"]) if df.get("size") else None,
                        md5_checksum=df.get("md5Checksum"),
                        modified_time=modified_time,
                        last_synced_at=datetime.now(timezone.utc),
                    )
                    session.add(file)

            # Soft delete files that are no longer in Drive
            for drive_id, file in existing_by_drive_id.items():
                if drive_id not in seen_drive_ids:
                    file.soft_delete()
                    session.add(file)

            folder.sync_status = "synced"
            folder.last_synced_at = datetime.now(timezone.utc)
            folder.sync_error = None
            session.add(folder)
            session.commit()

    except Exception as e:
        folder.sync_status = "error"
        folder.sync_error = str(e)
        session.add(folder)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {e}",
        )

    return SyncStatusResponse(
        folder_id=folder_id,
        sync_status=folder.sync_status,
        last_synced_at=folder.last_synced_at,
        error=folder.sync_error,
    )


# File Endpoints
@router.get("/folders/{folder_id}/files", response_model=List[DriveFileResponse])
def list_files(
    folder_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> List[DriveFileResponse]:
    """List files in a folder."""
    if current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated",
        )

    # Verify folder ownership
    folder = session.exec(
        select(DriveFolder).where(
            DriveFolder.id == folder_id,
            DriveFolder.user_id == current_user.id,
            DriveFolder.is_deleted == False,
        )
    ).first()

    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found",
        )

    files = session.exec(
        select(DriveFile).where(
            DriveFile.folder_id == folder_id,
            DriveFile.is_deleted == False,
        )
    ).all()

    return [
        DriveFileResponse(
            id=f.id,
            drive_file_id=f.drive_file_id,
            name=f.name,
            mime_type=f.mime_type,
            size=f.size,
            modified_time=f.modified_time,
            last_synced_at=f.last_synced_at,
        )
        for f in files
        if f.id is not None
    ]


@router.post("/folders/{folder_id}/files", response_model=DriveFileResponse)
async def upload_file(
    folder_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> DriveFileResponse:
    """Upload a file to Google Drive."""
    if current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated",
        )

    # Verify folder ownership
    folder = session.exec(
        select(DriveFolder).where(
            DriveFolder.id == folder_id,
            DriveFolder.user_id == current_user.id,
            DriveFolder.is_deleted == False,
        )
    ).first()

    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found",
        )

    try:
        access_token = await get_valid_access_token(session, current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    # Read file content
    content = await file.read()
    mime_type = file.content_type or "application/octet-stream"

    async with GoogleDriveClient(access_token) as client:
        try:
            result = await client.upload_file(
                name=file.filename or "untitled",
                content=content,
                mime_type=mime_type,
                folder_id=folder.drive_folder_id,
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Upload failed: {e}",
            )

    # Parse modified time
    modified_time = None
    if result.get("modifiedTime"):
        try:
            modified_time = datetime.fromisoformat(result["modifiedTime"].replace("Z", "+00:00"))
        except Exception:
            pass

    # Create file record
    drive_file = DriveFile(
        folder_id=folder_id,
        user_id=current_user.id,
        drive_file_id=result["id"],
        name=result["name"],
        mime_type=result.get("mimeType"),
        size=int(result["size"]) if result.get("size") else len(content),
        md5_checksum=result.get("md5Checksum"),
        modified_time=modified_time,
        last_synced_at=datetime.now(timezone.utc),
    )
    session.add(drive_file)
    session.commit()
    session.refresh(drive_file)

    if drive_file.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create file record",
        )
    return DriveFileResponse(
        id=drive_file.id,
        drive_file_id=drive_file.drive_file_id,
        name=drive_file.name,
        mime_type=drive_file.mime_type,
        size=drive_file.size,
        modified_time=drive_file.modified_time,
        last_synced_at=drive_file.last_synced_at,
    )


@router.get("/files/{file_id}", response_model=DriveFileResponse)
def get_file_metadata(
    file_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> DriveFileResponse:
    """Get file metadata."""
    if current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated",
        )

    file = session.exec(
        select(DriveFile).where(
            DriveFile.id == file_id,
            DriveFile.user_id == current_user.id,
            DriveFile.is_deleted == False,
        )
    ).first()

    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    return DriveFileResponse(
        id=file_id,
        drive_file_id=file.drive_file_id,
        name=file.name,
        mime_type=file.mime_type,
        size=file.size,
        modified_time=file.modified_time,
        last_synced_at=file.last_synced_at,
    )


@router.get("/files/{file_id}/download")
async def download_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> StreamingResponse:
    """Download file from Google Drive."""
    if current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated",
        )

    file = session.exec(
        select(DriveFile).where(
            DriveFile.id == file_id,
            DriveFile.user_id == current_user.id,
            DriveFile.is_deleted == False,
        )
    ).first()

    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    try:
        access_token = await get_valid_access_token(session, current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    async with GoogleDriveClient(access_token) as client:
        try:
            content = await client.download_file(file.drive_file_id)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Download failed: {e}",
            )

    return StreamingResponse(
        iter([content]),
        media_type=file.mime_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{file.name}"',
        },
    )


@router.patch("/files/{file_id}", response_model=DriveFileResponse)
async def rename_file(
    file_id: int,
    request: RenameFileRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> DriveFileResponse:
    """Rename a file."""
    if current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated",
        )

    file = session.exec(
        select(DriveFile).where(
            DriveFile.id == file_id,
            DriveFile.user_id == current_user.id,
            DriveFile.is_deleted == False,
        )
    ).first()

    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    try:
        access_token = await get_valid_access_token(session, current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    async with GoogleDriveClient(access_token) as client:
        try:
            await client.rename_file(file.drive_file_id, request.name)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Rename failed: {e}",
            )

    file.name = request.name
    file.update_timestamp()
    session.add(file)
    session.commit()
    session.refresh(file)

    return DriveFileResponse(
        id=file_id,
        drive_file_id=file.drive_file_id,
        name=file.name,
        mime_type=file.mime_type,
        size=file.size,
        modified_time=file.modified_time,
        last_synced_at=file.last_synced_at,
    )


@router.delete("/files/{file_id}")
async def delete_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Delete file from Google Drive."""
    if current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated",
        )

    file = session.exec(
        select(DriveFile).where(
            DriveFile.id == file_id,
            DriveFile.user_id == current_user.id,
            DriveFile.is_deleted == False,
        )
    ).first()

    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    try:
        access_token = await get_valid_access_token(session, current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    async with GoogleDriveClient(access_token) as client:
        try:
            await client.delete_file(file.drive_file_id)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Delete failed: {e}",
            )

    file.soft_delete()
    session.add(file)
    session.commit()

    return {"message": "File deleted"}


# Drive Browser Endpoints
@router.get("/browse", response_model=DriveBrowseResponse)
async def browse_drive(
    parent_id: Optional[str] = Query(None, description="Parent folder ID (None for root)"),
    page_token: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> DriveBrowseResponse:
    """Browse user's Drive folders."""
    if current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated",
        )

    try:
        access_token = await get_valid_access_token(session, current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    async with GoogleDriveClient(access_token) as client:
        try:
            result = await client.browse(folder_id=parent_id, page_token=page_token)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Browse failed: {e}",
            )

    items = []
    for f in result.get("files", []):
        mime_type = f.get("mimeType", "")
        is_folder = mime_type == GoogleDriveClient.FOLDER_MIME_TYPE

        # Parse modified time
        modified_time = None
        if f.get("modifiedTime"):
            try:
                modified_time = datetime.fromisoformat(f["modifiedTime"].replace("Z", "+00:00"))
            except Exception:
                pass

        items.append(
            DriveBrowseItem(
                id=f["id"],
                name=f["name"],
                mime_type=mime_type,
                is_folder=is_folder,
                modified_time=modified_time,
                size=int(f["size"]) if f.get("size") else None,
            )
        )

    return DriveBrowseResponse(
        items=items,
        next_page_token=result.get("nextPageToken"),
    )
