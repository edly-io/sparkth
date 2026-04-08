"""Integration tests for Google Drive API routes."""

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlmodel import Session

from app.models.drive import DriveFile, DriveFolder, DriveOAuthToken
from app.models.user import User
from app.rag.types import RagStatus

# ---------------------------------------------------------------------------
# OAuth Endpoints
# ---------------------------------------------------------------------------


class TestGetAuthorizationUrl:
    @pytest.mark.asyncio
    async def test_returns_url(self, drive_client: AsyncClient) -> None:
        """GET /oauth/authorize should return an authorization URL."""
        response = await drive_client.get("/api/v1/googledrive/oauth/authorize")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "url" in data
        assert "accounts.google.com" in data["url"]


class TestConnectionStatus:
    @pytest.mark.asyncio
    async def test_not_connected(self, drive_client: AsyncClient) -> None:
        """GET /oauth/status should return connected=false when no token."""
        response = await drive_client.get("/api/v1/googledrive/oauth/status")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["connected"] is False

    @pytest.mark.asyncio
    async def test_connected(
        self,
        drive_client: AsyncClient,
        test_oauth_token: DriveOAuthToken,
        mock_valid_access_token: None,
    ) -> None:
        """GET /oauth/status should return connected=true with email when token exists."""
        with patch(
            "app.core_plugins.googledrive.routes.get_user_info",
            new_callable=AsyncMock,
            return_value={"email": "user@gmail.com"},
        ):
            response = await drive_client.get("/api/v1/googledrive/oauth/status")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["connected"] is True
        assert data["email"] == "user@gmail.com"


class TestDisconnect:
    @pytest.mark.asyncio
    async def test_disconnect_not_connected(self, drive_client: AsyncClient) -> None:
        """DELETE /oauth/disconnect should return 404 when not connected."""
        response = await drive_client.delete("/api/v1/googledrive/oauth/disconnect")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_disconnect_success(
        self,
        drive_client: AsyncClient,
        test_oauth_token: DriveOAuthToken,
    ) -> None:
        """DELETE /oauth/disconnect should soft-delete token and revoke with Google."""
        with patch(
            "app.core_plugins.googledrive.routes.revoke_token",
            new_callable=AsyncMock,
            return_value=True,
        ):
            response = await drive_client.delete("/api/v1/googledrive/oauth/disconnect")

        assert response.status_code == status.HTTP_200_OK
        assert "disconnected" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Folder Endpoints
# ---------------------------------------------------------------------------


class TestListFolders:
    @pytest.mark.asyncio
    async def test_empty_list(self, drive_client: AsyncClient) -> None:
        """GET /folders should return empty list when no folders synced."""
        response = await drive_client.get("/api/v1/googledrive/folders")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_returns_synced_folders(
        self,
        drive_client: AsyncClient,
        test_folder: DriveFolder,
    ) -> None:
        """GET /folders should return synced folders with file count."""
        response = await drive_client.get("/api/v1/googledrive/folders")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Test Folder"
        assert data[0]["drive_folder_id"] == "drive_folder_abc123"
        assert data[0]["sync_status"] == "synced"

    @pytest.mark.asyncio
    async def test_excludes_deleted_folders(
        self,
        drive_client: AsyncClient,
        test_folder: DriveFolder,
        sync_session: Session,
    ) -> None:
        """GET /folders should not return soft-deleted folders."""
        test_folder.soft_delete()
        sync_session.add(test_folder)
        sync_session.commit()

        response = await drive_client.get("/api/v1/googledrive/folders")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []


class TestGetFolder:
    @pytest.mark.asyncio
    async def test_get_folder_with_files(
        self,
        drive_client: AsyncClient,
        test_folder: DriveFolder,
        test_file: DriveFile,
    ) -> None:
        """GET /folders/{id} should return folder with its files."""
        response = await drive_client.get(f"/api/v1/googledrive/folders/{test_folder.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Test Folder"
        assert data["file_count"] == 1
        assert len(data["files"]) == 1
        assert data["files"][0]["name"] == "test_document.pdf"

    @pytest.mark.asyncio
    async def test_get_folder_not_found(self, drive_client: AsyncClient) -> None:
        """GET /folders/{id} should return 404 for non-existent folder."""
        response = await drive_client.get("/api/v1/googledrive/folders/99999")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_excludes_deleted_files(
        self,
        drive_client: AsyncClient,
        test_folder: DriveFolder,
        test_file: DriveFile,
        sync_session: Session,
    ) -> None:
        """GET /folders/{id} should not include soft-deleted files."""
        test_file.soft_delete()
        sync_session.add(test_file)
        sync_session.commit()

        response = await drive_client.get(f"/api/v1/googledrive/folders/{test_folder.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["file_count"] == 0
        assert data["files"] == []


class TestDeleteFolder:
    @pytest.mark.asyncio
    async def test_soft_deletes_folder_and_files(
        self,
        drive_client: AsyncClient,
        test_folder: DriveFolder,
        test_file: DriveFile,
    ) -> None:
        """DELETE /folders/{id} should soft-delete folder and its files."""
        response = await drive_client.delete(f"/api/v1/googledrive/folders/{test_folder.id}")

        assert response.status_code == status.HTTP_200_OK
        assert "removed" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_delete_nonexistent_folder(self, drive_client: AsyncClient) -> None:
        """DELETE /folders/{id} should return 404 for non-existent folder."""
        response = await drive_client.delete("/api/v1/googledrive/folders/99999")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestSyncFolder:
    @pytest.mark.asyncio
    async def test_sync_new_folder(
        self,
        drive_client: AsyncClient,
        test_oauth_token: DriveOAuthToken,
        mock_valid_access_token: None,
    ) -> None:
        """POST /folders/sync should create and sync a new folder."""
        folder_metadata = {
            "id": "new_drive_folder_id",
            "name": "My Folder",
            "parents": ["root"],
        }

        with (
            patch("app.core_plugins.googledrive.routes.GoogleDriveClient") as mock_client_cls,
            patch("app.core_plugins.googledrive.routes.process_folder_rag", new_callable=AsyncMock),
        ):
            mock_client = AsyncMock()
            mock_client.get_folder.return_value = folder_metadata
            mock_client.list_files.return_value = {"files": []}
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_cls.return_value = mock_client

            response = await drive_client.post(
                "/api/v1/googledrive/folders/sync",
                json={"drive_folder_id": "new_drive_folder_id"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "My Folder"
        assert data["drive_folder_id"] == "new_drive_folder_id"

    @pytest.mark.asyncio
    async def test_sync_already_synced_folder(
        self,
        drive_client: AsyncClient,
        test_folder: DriveFolder,
        test_oauth_token: DriveOAuthToken,
        mock_valid_access_token: None,
    ) -> None:
        """POST /folders/sync should return 409 if folder already synced."""
        response = await drive_client.post(
            "/api/v1/googledrive/folders/sync",
            json={"drive_folder_id": "drive_folder_abc123"},
        )

        assert response.status_code == status.HTTP_409_CONFLICT


class TestRefreshFolder:
    @pytest.mark.asyncio
    async def test_refresh_success(
        self,
        drive_client: AsyncClient,
        test_folder: DriveFolder,
        test_oauth_token: DriveOAuthToken,
        mock_valid_access_token: None,
    ) -> None:
        """POST /folders/{id}/refresh should re-sync files from Drive."""
        with (
            patch("app.core_plugins.googledrive.routes.GoogleDriveClient") as mock_client_cls,
            patch("app.core_plugins.googledrive.routes.process_folder_rag", new_callable=AsyncMock),
        ):
            mock_client = AsyncMock()
            mock_client.list_files.return_value = {
                "files": [
                    {
                        "id": "new_file_1",
                        "name": "synced.pdf",
                        "mimeType": "application/pdf",
                        "size": "512",
                    }
                ]
            }
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_cls.return_value = mock_client

            response = await drive_client.post(f"/api/v1/googledrive/folders/{test_folder.id}/refresh")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["sync_status"] == "synced"

    @pytest.mark.asyncio
    async def test_refresh_nonexistent_folder(
        self,
        drive_client: AsyncClient,
        test_oauth_token: DriveOAuthToken,
    ) -> None:
        """POST /folders/{id}/refresh should return 404 for non-existent folder."""
        response = await drive_client.post("/api/v1/googledrive/folders/99999/refresh")

        assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# File Endpoints
# ---------------------------------------------------------------------------


class TestListFiles:
    @pytest.mark.asyncio
    async def test_list_files_in_folder(
        self,
        drive_client: AsyncClient,
        test_folder: DriveFolder,
        test_file: DriveFile,
    ) -> None:
        """GET /folders/{id}/files should return files in the folder."""
        response = await drive_client.get(f"/api/v1/googledrive/folders/{test_folder.id}/files")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "test_document.pdf"
        assert data[0]["mime_type"] == "application/pdf"

    @pytest.mark.asyncio
    async def test_list_files_folder_not_found(self, drive_client: AsyncClient) -> None:
        """GET /folders/{id}/files should return 404 for non-existent folder."""
        response = await drive_client.get("/api/v1/googledrive/folders/99999/files")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestGetFile:
    @pytest.mark.asyncio
    async def test_get_file_metadata(
        self,
        drive_client: AsyncClient,
        test_file: DriveFile,
    ) -> None:
        """GET /files/{id} should return file metadata."""
        response = await drive_client.get(f"/api/v1/googledrive/files/{test_file.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "test_document.pdf"
        assert data["drive_file_id"] == "drive_file_xyz789"
        assert data["size"] == 1024

    @pytest.mark.asyncio
    async def test_get_file_not_found(self, drive_client: AsyncClient) -> None:
        """GET /files/{id} should return 404 for non-existent file."""
        response = await drive_client.get("/api/v1/googledrive/files/99999")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestDownloadFile:
    @pytest.mark.asyncio
    async def test_download_success(
        self,
        drive_client: AsyncClient,
        test_file: DriveFile,
        test_oauth_token: DriveOAuthToken,
        mock_valid_access_token: None,
    ) -> None:
        """GET /files/{id}/download should stream file content."""

        async def _fake_stream(*args: Any, **kwargs: Any) -> AsyncGenerator[bytes, None]:
            yield b"file content"

        with patch("app.core_plugins.googledrive.routes.GoogleDriveClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.stream_download = _fake_stream
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_cls.return_value = mock_client

            response = await drive_client.get(f"/api/v1/googledrive/files/{test_file.id}/download")

        assert response.status_code == status.HTTP_200_OK
        assert response.content == b"file content"
        assert "attachment" in response.headers.get("content-disposition", "")

    @pytest.mark.asyncio
    async def test_download_google_doc_exports_pdf(
        self,
        drive_client: AsyncClient,
        test_oauth_token: DriveOAuthToken,
        mock_valid_access_token: None,
        sync_session: Session,
        test_user: User,
        test_folder: DriveFolder,
    ) -> None:
        """Downloading a Google Doc should return PDF with adjusted filename."""
        # Create a Google Docs file directly (not reusing test_file)
        doc_file = DriveFile(
            folder_id=cast(int, test_folder.id),
            user_id=cast(int, test_user.id),
            drive_file_id="drive_doc_id",
            name="My Doc",
            mime_type="application/vnd.google-apps.document",
            size=None,
            last_synced_at=datetime.now(timezone.utc),
        )
        sync_session.add(doc_file)
        sync_session.commit()
        sync_session.refresh(doc_file)

        from app.core_plugins.googledrive.client import GoogleDriveClient as RealClient

        async def _fake_stream(*args: Any, **kwargs: Any) -> AsyncGenerator[bytes, None]:
            yield b"%PDF-1.4"

        with patch("app.core_plugins.googledrive.routes.GoogleDriveClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.stream_download = _fake_stream
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_cls.return_value = mock_client
            mock_client_cls.EXPORT_MIME_MAP = RealClient.EXPORT_MIME_MAP

            response = await drive_client.get(f"/api/v1/googledrive/files/{doc_file.id}/download")

        assert response.status_code == status.HTTP_200_OK
        assert "application/pdf" in response.headers.get("content-type", "")
        assert "My Doc.pdf" in response.headers.get("content-disposition", "")

    @pytest.mark.asyncio
    async def test_download_file_not_found(
        self,
        drive_client: AsyncClient,
    ) -> None:
        """GET /files/{id}/download should return 404 for non-existent file."""
        response = await drive_client.get("/api/v1/googledrive/files/99999/download")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_download_drive_error_returns_502(
        self,
        drive_client: AsyncClient,
        test_file: DriveFile,
        test_oauth_token: DriveOAuthToken,
        mock_valid_access_token: None,
    ) -> None:
        """Drive API error during download should propagate (connection closes abruptly)."""

        async def _failing_stream(*args: Any, **kwargs: Any) -> AsyncGenerator[bytes, None]:
            raise RuntimeError("Drive API error")
            yield  # noqa: RET503 — make this an async generator

        with patch("app.core_plugins.googledrive.routes.GoogleDriveClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.stream_download = _failing_stream
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_cls.return_value = mock_client

            with pytest.raises(RuntimeError, match="Drive API error"):
                await drive_client.get(f"/api/v1/googledrive/files/{test_file.id}/download")


class TestRenameFile:
    @pytest.mark.asyncio
    async def test_rename_success(
        self,
        drive_client: AsyncClient,
        test_file: DriveFile,
        test_oauth_token: DriveOAuthToken,
        mock_valid_access_token: None,
    ) -> None:
        """PATCH /files/{id} should rename file in Drive and DB."""
        with patch("app.core_plugins.googledrive.routes.GoogleDriveClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.rename_file.return_value = {"id": "f1", "name": "renamed.pdf"}
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_cls.return_value = mock_client

            response = await drive_client.patch(
                f"/api/v1/googledrive/files/{test_file.id}",
                json={"name": "renamed.pdf"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "renamed.pdf"

    @pytest.mark.asyncio
    async def test_rename_file_not_found(self, drive_client: AsyncClient) -> None:
        """PATCH /files/{id} should return 404 for non-existent file."""
        response = await drive_client.patch(
            "/api/v1/googledrive/files/99999",
            json={"name": "new_name.pdf"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_rename_drive_error_returns_502(
        self,
        drive_client: AsyncClient,
        test_file: DriveFile,
        test_oauth_token: DriveOAuthToken,
        mock_valid_access_token: None,
    ) -> None:
        """Drive API error during rename should return 502."""
        with patch("app.core_plugins.googledrive.routes.GoogleDriveClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.rename_file.side_effect = RuntimeError("403 Forbidden")
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_cls.return_value = mock_client

            response = await drive_client.patch(
                f"/api/v1/googledrive/files/{test_file.id}",
                json={"name": "renamed.pdf"},
            )

        assert response.status_code == status.HTTP_502_BAD_GATEWAY


class TestDeleteFile:
    @pytest.mark.asyncio
    async def test_delete_marks_file_as_deleted(
        self,
        drive_client: AsyncClient,
        test_file: DriveFile,
        sync_session: Session,
    ) -> None:
        """DELETE /files/{id} should soft-delete locally; file remains in Google Drive."""
        response = await drive_client.delete(f"/api/v1/googledrive/files/{test_file.id}")

        assert response.status_code == status.HTTP_200_OK
        assert "removed" in response.json()["detail"].lower()

        sync_session.refresh(test_file)
        assert test_file.is_deleted is True
        assert test_file.deleted_at is not None

    @pytest.mark.asyncio
    async def test_deleted_file_no_longer_accessible(
        self,
        drive_client: AsyncClient,
        test_file: DriveFile,
    ) -> None:
        """File should return 404 on GET after deletion."""
        await drive_client.delete(f"/api/v1/googledrive/files/{test_file.id}")

        response = await drive_client.get(f"/api/v1/googledrive/files/{test_file.id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_file_not_found(self, drive_client: AsyncClient) -> None:
        """DELETE /files/{id} should return 404 for non-existent file."""
        response = await drive_client.delete("/api/v1/googledrive/files/99999")

        assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# RAG Status Endpoints
# ---------------------------------------------------------------------------


class TestGetFileRagStatus:
    @pytest.mark.asyncio
    async def test_returns_null_when_not_processed(
        self,
        drive_client: AsyncClient,
        test_file: DriveFile,
    ) -> None:
        """GET /files/{id}/rag-status should return null rag_status for unprocessed files."""
        response = await drive_client.get(f"/api/v1/googledrive/files/{test_file.id}/rag-status")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["file_id"] == test_file.id
        assert data["name"] == "test_document.pdf"
        assert data["rag_status"] is None

    @pytest.mark.asyncio
    async def test_returns_processing_status(
        self,
        drive_client: AsyncClient,
        test_file: DriveFile,
        sync_session: Session,
    ) -> None:
        """GET /files/{id}/rag-status should return 'processing' while pipeline runs."""
        test_file.rag_status = RagStatus.PROCESSING
        sync_session.add(test_file)
        sync_session.commit()

        response = await drive_client.get(f"/api/v1/googledrive/files/{test_file.id}/rag-status")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["rag_status"] == "processing"

    @pytest.mark.asyncio
    async def test_returns_ready_status(
        self,
        drive_client: AsyncClient,
        test_file: DriveFile,
        sync_session: Session,
    ) -> None:
        """GET /files/{id}/rag-status should return 'ready' when processing is complete."""
        test_file.rag_status = RagStatus.READY
        sync_session.add(test_file)
        sync_session.commit()

        response = await drive_client.get(f"/api/v1/googledrive/files/{test_file.id}/rag-status")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["rag_status"] == "ready"

    @pytest.mark.asyncio
    async def test_returns_failed_status(
        self,
        drive_client: AsyncClient,
        test_file: DriveFile,
        sync_session: Session,
    ) -> None:
        """GET /files/{id}/rag-status should return 'failed' when processing errored."""
        test_file.rag_status = RagStatus.FAILED
        sync_session.add(test_file)
        sync_session.commit()

        response = await drive_client.get(f"/api/v1/googledrive/files/{test_file.id}/rag-status")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["rag_status"] == "failed"

    @pytest.mark.asyncio
    async def test_file_not_found(self, drive_client: AsyncClient) -> None:
        """GET /files/{id}/rag-status should return 404 for non-existent file."""
        response = await drive_client.get("/api/v1/googledrive/files/99999/rag-status")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_deleted_file_returns_404(
        self,
        drive_client: AsyncClient,
        test_file: DriveFile,
        sync_session: Session,
    ) -> None:
        """GET /files/{id}/rag-status should return 404 for soft-deleted files."""
        test_file.soft_delete()
        sync_session.add(test_file)
        sync_session.commit()

        response = await drive_client.get(f"/api/v1/googledrive/files/{test_file.id}/rag-status")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestGetFolderRagStatus:
    @pytest.mark.asyncio
    async def test_returns_statuses_for_all_files(
        self,
        drive_client: AsyncClient,
        test_folder: DriveFolder,
        test_file: DriveFile,
        sync_session: Session,
        test_user: User,
    ) -> None:
        """GET /folders/{id}/rag-status should return rag_status for every file."""
        test_file.rag_status = RagStatus.READY
        second_file = DriveFile(
            folder_id=cast(int, test_folder.id),
            user_id=cast(int, test_user.id),
            drive_file_id="drive_file_second",
            name="slides.pdf",
            mime_type="application/pdf",
            size=512,
            rag_status=RagStatus.PROCESSING,
            last_synced_at=test_file.last_synced_at,
        )
        sync_session.add(test_file)
        sync_session.add(second_file)
        sync_session.commit()

        response = await drive_client.get(f"/api/v1/googledrive/folders/{test_folder.id}/rag-status")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["folder_id"] == test_folder.id
        statuses = {f["name"]: f["rag_status"] for f in data["files"]}
        assert statuses["test_document.pdf"] == "ready"
        assert statuses["slides.pdf"] == "processing"

    @pytest.mark.asyncio
    async def test_empty_folder_returns_empty_list(
        self,
        drive_client: AsyncClient,
        test_folder: DriveFolder,
    ) -> None:
        """GET /folders/{id}/rag-status should return empty files list for a folder with no files."""
        response = await drive_client.get(f"/api/v1/googledrive/folders/{test_folder.id}/rag-status")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["folder_id"] == test_folder.id
        assert data["files"] == []

    @pytest.mark.asyncio
    async def test_folder_not_found(self, drive_client: AsyncClient) -> None:
        """GET /folders/{id}/rag-status should return 404 for non-existent folder."""
        response = await drive_client.get("/api/v1/googledrive/folders/99999/rag-status")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_excludes_deleted_files(
        self,
        drive_client: AsyncClient,
        test_folder: DriveFolder,
        test_file: DriveFile,
        sync_session: Session,
        test_user: User,
    ) -> None:
        """GET /folders/{id}/rag-status should exclude soft-deleted files."""
        # Create two files, one active and one deleted
        test_file.rag_status = RagStatus.READY
        deleted_file = DriveFile(
            folder_id=cast(int, test_folder.id),
            user_id=cast(int, test_user.id),
            drive_file_id="drive_file_deleted",
            name="deleted_doc.pdf",
            mime_type="application/pdf",
            size=1024,
            rag_status=RagStatus.READY,
            last_synced_at=test_file.last_synced_at,
        )
        deleted_file.soft_delete()
        sync_session.add(test_file)
        sync_session.add(deleted_file)
        sync_session.commit()

        response = await drive_client.get(f"/api/v1/googledrive/folders/{test_folder.id}/rag-status")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["files"]) == 1
        assert data["files"][0]["name"] == "test_document.pdf"


class TestBrowseDrive:
    @pytest.mark.asyncio
    async def test_browse_root(
        self,
        drive_client: AsyncClient,
        test_oauth_token: DriveOAuthToken,
        mock_valid_access_token: None,
    ) -> None:
        """GET /browse should list files and folders from Drive root."""
        browse_result = {
            "files": [
                {
                    "id": "folder_1",
                    "name": "Documents",
                    "mimeType": "application/vnd.google-apps.folder",
                },
                {
                    "id": "file_1",
                    "name": "report.pdf",
                    "mimeType": "application/pdf",
                    "size": "2048",
                    "modifiedTime": "2024-01-15T10:00:00Z",
                },
            ],
        }

        with patch("app.core_plugins.googledrive.routes.GoogleDriveClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.browse.return_value = browse_result
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_cls.return_value = mock_client
            # Preserve FOLDER_MIME_TYPE so is_folder check works
            mock_client_cls.FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"

            response = await drive_client.get("/api/v1/googledrive/browse")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["items"]) == 2
        assert data["items"][0]["is_folder"] is True
        assert data["items"][0]["name"] == "Documents"
        assert data["items"][1]["is_folder"] is False
        assert data["items"][1]["size"] == 2048

    @pytest.mark.asyncio
    async def test_browse_subfolder(
        self,
        drive_client: AsyncClient,
        test_oauth_token: DriveOAuthToken,
        mock_valid_access_token: None,
    ) -> None:
        """GET /browse?folder_id=X should browse a specific folder."""
        with patch("app.core_plugins.googledrive.routes.GoogleDriveClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.browse.return_value = {"files": []}
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_cls.return_value = mock_client

            response = await drive_client.get("/api/v1/googledrive/browse?folder_id=subfolder_123")

        assert response.status_code == status.HTTP_200_OK
        mock_client.browse.assert_called_once_with(folder_id="subfolder_123", page_token=None)
