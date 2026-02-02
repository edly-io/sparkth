"""Pydantic models for Google Drive plugin requests and responses."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# Request models
class SyncFolderRequest(BaseModel):
    """Request to sync a Google Drive folder."""

    drive_folder_id: str = Field(..., description="Google Drive folder ID to sync")


class CreateFolderRequest(BaseModel):
    """Request to create a new folder in Google Drive."""

    name: str = Field(..., description="Name of the folder to create")
    parent_id: Optional[str] = Field(None, description="Parent folder ID in Google Drive")


class RenameFileRequest(BaseModel):
    """Request to rename a file."""

    name: str = Field(..., description="New name for the file")


# Response models
class ConnectionStatusResponse(BaseModel):
    """Google Drive connection status."""

    connected: bool
    email: Optional[str] = None
    expires_at: Optional[datetime] = None


class AuthorizationUrlResponse(BaseModel):
    """OAuth authorization URL response."""

    url: str


class DriveFolderResponse(BaseModel):
    """Google Drive folder metadata."""

    id: int
    drive_folder_id: str
    name: str
    parent_id: Optional[str] = None
    file_count: int = 0
    last_synced_at: Optional[datetime] = None
    sync_status: str


class DriveFileResponse(BaseModel):
    """Google Drive file metadata."""

    id: int
    drive_file_id: str
    name: str
    mime_type: Optional[str] = None
    size: Optional[int] = None
    modified_time: Optional[datetime] = None
    last_synced_at: Optional[datetime] = None


class DriveFolderWithFilesResponse(DriveFolderResponse):
    """Folder with its files."""

    files: list[DriveFileResponse] = []


class SyncStatusResponse(BaseModel):
    """Sync operation status."""

    folder_id: int
    sync_status: str
    last_synced_at: Optional[datetime] = None
    error: Optional[str] = None


class DriveBrowseItem(BaseModel):
    """Item in Drive browser (folder or file)."""

    id: str
    name: str
    mime_type: str
    is_folder: bool
    modified_time: Optional[datetime] = None
    size: Optional[int] = None


class DriveBrowseResponse(BaseModel):
    """Response for browsing Drive folders."""

    items: list[DriveBrowseItem] = []
    next_page_token: Optional[str] = None
