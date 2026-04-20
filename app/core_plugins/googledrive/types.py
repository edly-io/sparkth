"""Pydantic models for Google Drive plugin requests and responses."""

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from app.rag.types import RagStatus

T = TypeVar("T")


# Request models
class SyncFolderRequest(BaseModel):
    """Request to sync a Google Drive folder."""

    drive_folder_id: str = Field(..., description="Google Drive folder ID to sync")


class CreateFolderRequest(BaseModel):
    """Request to create a new folder in Google Drive."""

    name: str = Field(..., description="Name of the folder to create")
    parent_id: str | None = Field(None, description="Parent folder ID in Google Drive")


class RenameFileRequest(BaseModel):
    """Request to rename a file."""

    name: str = Field(..., description="New name for the file")


# Response models
class ConnectionStatusResponse(BaseModel):
    """Google Drive connection status."""

    connected: bool
    email: str | None = None
    expires_at: datetime | None = None


class AuthorizationUrlResponse(BaseModel):
    """OAuth authorization URL response."""

    url: str


class DriveFolderResponse(BaseModel):
    """Google Drive folder metadata."""

    id: int
    drive_folder_id: str
    name: str
    parent_id: str | None = None
    file_count: int = 0
    last_synced_at: datetime | None = None
    sync_status: str


class DriveFileResponse(BaseModel):
    """Google Drive file metadata."""

    id: int
    drive_file_id: str
    name: str
    mime_type: str | None = None
    size: int | None = None
    modified_time: datetime | None = None
    last_synced_at: datetime | None = None


class DriveFolderWithFilesResponse(DriveFolderResponse):
    """Folder with its files."""

    files: list[DriveFileResponse] = []


class SyncStatusResponse(BaseModel):
    """Sync operation status."""

    folder_id: int
    sync_status: str
    last_synced_at: datetime | None = None
    error: str | None = None


class DriveBrowseItem(BaseModel):
    """Item in Drive browser (folder or file)."""

    id: str
    name: str
    mime_type: str
    is_folder: bool
    modified_time: datetime | None = None
    size: int | None = None


class DriveBrowseResponse(BaseModel):
    """Response for browsing Drive folders."""

    items: list[DriveBrowseItem] = []
    next_page_token: str | None = None


class FileRagStatusResponse(BaseModel):
    """RAG processing status for a single file."""

    file_id: int
    name: str
    rag_status: RagStatus | None = None
    rag_error: str | None = None


class FolderRagStatusResponse(BaseModel):
    """RAG processing status for all files in a folder."""

    folder_id: int
    files: list[FileRagStatusResponse] = []


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""

    items: list[T] = []
    total: int = 0
    skip: int = 0
    limit: int = 20
