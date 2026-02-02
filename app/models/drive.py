"""
Google Drive models for OAuth tokens, folders, and file metadata.
"""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, Relationship

from app.models.base import SoftDeleteModel, TimestampedModel


class DriveOAuthToken(TimestampedModel, SoftDeleteModel, table=True):
    """
    Stores encrypted OAuth tokens per user for Google Drive access.
    """

    __tablename__ = "drive_oauth_tokens"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True, index=True)

    access_token_encrypted: str = Field(max_length=2000)
    refresh_token_encrypted: str = Field(max_length=2000)
    token_expiry: datetime
    scopes: str = Field(max_length=1000)


class DriveFolder(TimestampedModel, SoftDeleteModel, table=True):
    """
    Tracks synced Google Drive folders.
    """

    __tablename__ = "drive_folders"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)

    drive_folder_id: str = Field(max_length=255, index=True)
    drive_folder_name: str = Field(max_length=500)
    drive_parent_id: Optional[str] = Field(default=None, max_length=255)

    last_synced_at: Optional[datetime] = Field(default=None)
    sync_status: str = Field(default="pending", max_length=50)
    sync_error: Optional[str] = Field(default=None)

    files: list["DriveFile"] = Relationship(back_populates="folder")


class DriveFile(TimestampedModel, SoftDeleteModel, table=True):
    """
    Tracks file metadata (files are stored only in Google Drive).
    """

    __tablename__ = "drive_files"

    id: Optional[int] = Field(default=None, primary_key=True)
    folder_id: int = Field(foreign_key="drive_folders.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)

    drive_file_id: str = Field(max_length=255, index=True)
    name: str = Field(max_length=500)
    mime_type: Optional[str] = Field(default=None, max_length=255)
    size: Optional[int] = Field(default=None)
    md5_checksum: Optional[str] = Field(default=None, max_length=64)
    modified_time: Optional[datetime] = Field(default=None)

    last_synced_at: Optional[datetime] = Field(default=None)

    folder: "DriveFolder" = Relationship(back_populates="files")
