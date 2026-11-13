"""Integration tests for Google Drive API routes."""

from collections.abc import AsyncGenerator, Iterator
from datetime import datetime, timezone
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import delete
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.permissions.models import RoleAssignment
from sparkth.lib.documents import Document, DocumentStatus
from sparkth.lib.models import User
from sparkth.lib.permissions.scopes import GLOBAL, USER
from sparkth.lib.testing import AuditEventsFetcher, grant_permission_at_scope, make_user
from sparkth.plugins.googledrive.models import DriveFile, DriveFolder, DriveOAuthToken

# ---------------------------------------------------------------------------
# OAuth Endpoints
# ---------------------------------------------------------------------------


class TestGetAuthorizationUrl:
    @pytest.mark.asyncio
    async def test_returns_url(self, drive_client: AsyncClient) -> None:
        """GET /oauth/authorize should return an authorization URL."""
        response = await drive_client.get("/api/v1/google-drive/oauth/authorize")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "url" in data
        assert "accounts.google.com" in data["url"]


class TestCallback:
    @pytest.mark.asyncio
    async def test_redirects_to_the_drive_page(self, drive_client: AsyncClient, test_user: User) -> None:
        """GET /oauth/callback should send the user back to the Google Drive page once connected."""
        token_data = {"access_token": "access", "refresh_token": "refresh", "expires_in": 3600, "scope": ""}
        with (
            patch("sparkth.plugins.googledrive.routes.oauth.decode_state", return_value={"user_id": test_user.id}),
            patch(
                "sparkth.plugins.googledrive.routes.oauth.exchange_code_for_tokens",
                new_callable=AsyncMock,
                return_value=token_data,
            ),
        ):
            response = await drive_client.get(
                "/api/v1/google-drive/oauth/callback",
                params={"code": "code", "state": "state"},
                follow_redirects=False,
            )

        assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
        assert response.headers["location"] == "/dashboard/google-drive?connected=true"


class TestConnectionStatus:
    @pytest.mark.asyncio
    async def test_not_connected(self, drive_client: AsyncClient) -> None:
        """GET /oauth/status should return connected=false when no token."""
        response = await drive_client.get("/api/v1/google-drive/oauth/status")

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
            "sparkth.plugins.googledrive.routes.oauth.get_user_info",
            new_callable=AsyncMock,
            return_value={"email": "user@gmail.com"},
        ):
            response = await drive_client.get("/api/v1/google-drive/oauth/status")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["connected"] is True
        assert data["email"] == "user@gmail.com"


class TestDisconnect:
    @pytest.mark.asyncio
    async def test_disconnect_not_connected(self, drive_client: AsyncClient) -> None:
        """DELETE /oauth/disconnect should return 404 when not connected."""
        response = await drive_client.delete("/api/v1/google-drive/oauth/disconnect")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_disconnect_success(
        self,
        drive_client: AsyncClient,
        test_oauth_token: DriveOAuthToken,
    ) -> None:
        """DELETE /oauth/disconnect should soft-delete token and revoke with Google."""
        with patch(
            "sparkth.plugins.googledrive.routes.oauth.revoke_token",
            new_callable=AsyncMock,
            return_value=True,
        ):
            response = await drive_client.delete("/api/v1/google-drive/oauth/disconnect")

        assert response.status_code == status.HTTP_200_OK
        assert "disconnected" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Folder Endpoints
# ---------------------------------------------------------------------------


class TestListFolders:
    @pytest.mark.asyncio
    async def test_empty_list(self, drive_client: AsyncClient) -> None:
        """GET /folders should return empty list when no folders synced."""
        response = await drive_client.get("/api/v1/google-drive/folders")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_returns_synced_folders(
        self,
        drive_client: AsyncClient,
        test_folder: DriveFolder,
    ) -> None:
        """GET /folders should return synced folders with file count."""
        response = await drive_client.get("/api/v1/google-drive/folders")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "Test Folder"
        assert data["items"][0]["drive_folder_id"] == "drive_folder_abc123"
        assert data["items"][0]["sync_status"] == "synced"

    @pytest.mark.asyncio
    async def test_excludes_deleted_folders(
        self,
        drive_client: AsyncClient,
        test_folder: DriveFolder,
        session: AsyncSession,
    ) -> None:
        """GET /folders should not return soft-deleted folders."""
        test_folder.soft_delete()
        session.add(test_folder)
        await session.flush()

        response = await drive_client.get("/api/v1/google-drive/folders")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0


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
            patch("sparkth.plugins.googledrive.routes.folders.GoogleDriveClient") as mock_client_cls,
            patch("sparkth.plugins.googledrive.routes.folders.process_folder_rag", new_callable=AsyncMock),
        ):
            mock_client = AsyncMock()
            mock_client.get_folder.return_value = folder_metadata
            mock_client.list_files.return_value = {"files": []}
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_cls.return_value = mock_client

            response = await drive_client.post(
                "/api/v1/google-drive/folders/sync",
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
            "/api/v1/google-drive/folders/sync",
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
            patch("sparkth.plugins.googledrive.routes.folders.GoogleDriveClient") as mock_client_cls,
            patch("sparkth.plugins.googledrive.routes.folders.process_folder_rag", new_callable=AsyncMock),
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
            mock_client_cls.FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"

            response = await drive_client.post(f"/api/v1/google-drive/folders/{test_folder.id}/refresh")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["sync_status"] == "synced"

    @pytest.mark.asyncio
    async def test_refresh_skips_subfolder_items(
        self,
        drive_client: AsyncClient,
        test_folder: DriveFolder,
        test_oauth_token: DriveOAuthToken,
        mock_valid_access_token: None,
        session: AsyncSession,
    ) -> None:
        """Subfolder entries returned by the Drive API must not be stored as DriveFiles."""
        with (
            patch("sparkth.plugins.googledrive.routes.folders.GoogleDriveClient") as mock_client_cls,
            patch("sparkth.plugins.googledrive.routes.folders.process_folder_rag", new_callable=AsyncMock),
        ):
            mock_client = AsyncMock()
            mock_client.list_files.return_value = {
                "files": [
                    {
                        "id": "real_file_1",
                        "name": "lecture.pdf",
                        "mimeType": "application/pdf",
                        "size": "1024",
                    },
                    {
                        "id": "subfolder_1",
                        "name": "Week 1",
                        "mimeType": "application/vnd.google-apps.folder",
                    },
                ]
            }
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_cls.return_value = mock_client
            mock_client_cls.FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"

            response = await drive_client.post(f"/api/v1/google-drive/folders/{test_folder.id}/refresh")

        assert response.status_code == status.HTTP_200_OK
        stored = (await session.exec(select(DriveFile).where(DriveFile.folder_id == test_folder.id))).all()
        stored_ids = {f.drive_file_id for f in stored}
        assert "real_file_1" in stored_ids
        assert "subfolder_1" not in stored_ids

    @pytest.mark.asyncio
    async def test_refresh_nonexistent_folder(
        self,
        drive_client: AsyncClient,
        test_oauth_token: DriveOAuthToken,
    ) -> None:
        """POST /folders/{id}/refresh should return 404 for non-existent folder."""
        response = await drive_client.post("/api/v1/google-drive/folders/99999/refresh")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_refresh_soft_deletes_document_of_removed_file(
        self,
        drive_client: AsyncClient,
        test_folder: DriveFolder,
        test_file: DriveFile,
        test_user: User,
        test_oauth_token: DriveOAuthToken,
        mock_valid_access_token: None,
        session: AsyncSession,
    ) -> None:
        """A file gone from Drive has its DriveFile and linked Document soft-deleted."""
        document = Document(user_id=cast(int, test_user.id), name="linked.pdf")
        session.add(document)
        await session.commit()
        await session.refresh(document)
        test_file.document_id = document.id
        session.add(test_file)
        await session.commit()

        with (
            patch("sparkth.plugins.googledrive.routes.folders.GoogleDriveClient") as mock_client_cls,
            patch("sparkth.plugins.googledrive.routes.folders.process_folder_rag", new_callable=AsyncMock),
        ):
            mock_client = AsyncMock()
            mock_client.list_files.return_value = {"files": []}
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_cls.return_value = mock_client
            mock_client_cls.FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"

            response = await drive_client.post(f"/api/v1/google-drive/folders/{test_folder.id}/refresh")

        assert response.status_code == status.HTTP_200_OK
        await session.refresh(test_file)
        await session.refresh(document)
        assert test_file.is_deleted is True
        assert document.is_deleted is True


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
        response = await drive_client.get(f"/api/v1/google-drive/folders/{test_folder.id}/files")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "test_document.pdf"
        assert data["items"][0]["mime_type"] == "application/pdf"

    @pytest.mark.asyncio
    async def test_list_files_includes_rag_status(
        self,
        drive_client: AsyncClient,
        test_folder: DriveFolder,
        test_file: DriveFile,
        session: AsyncSession,
        test_user: User,
    ) -> None:
        """GET /folders/{id}/files should include rag_status for each file."""
        doc = Document(user_id=cast(int, test_user.id), name="test_document.pdf", status=DocumentStatus.READY)
        session.add(doc)
        await session.flush()
        await session.refresh(doc)
        assert test_folder.id is not None
        folder_id = test_folder.id
        test_file.document_id = doc.id
        session.add(test_file)
        await session.commit()

        response = await drive_client.get(f"/api/v1/google-drive/folders/{folder_id}/files")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["items"][0]["rag_status"] == "ready"
        assert data["items"][0]["rag_error"] is None

    @pytest.mark.asyncio
    async def test_list_files_folder_not_found(self, drive_client: AsyncClient) -> None:
        """GET /folders/{id}/files should return 404 for non-existent folder."""
        response = await drive_client.get("/api/v1/google-drive/folders/99999/files")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestGetFile:
    @pytest.mark.asyncio
    async def test_get_file_metadata(
        self,
        drive_client: AsyncClient,
        test_file: DriveFile,
    ) -> None:
        """GET /files/{id} should return file metadata."""
        response = await drive_client.get(f"/api/v1/google-drive/files/{test_file.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "test_document.pdf"
        assert data["drive_file_id"] == "drive_file_xyz789"
        assert data["size"] == 1024

    @pytest.mark.asyncio
    async def test_get_file_includes_rag_status(
        self,
        drive_client: AsyncClient,
        test_file: DriveFile,
        session: AsyncSession,
        test_user: User,
    ) -> None:
        """GET /files/{id} should include rag_status and rag_error fields."""
        doc = Document(user_id=cast(int, test_user.id), name="test_document.pdf", status=DocumentStatus.PROCESSING)
        session.add(doc)
        await session.flush()
        await session.refresh(doc)
        assert test_file.id is not None
        file_id = test_file.id
        test_file.document_id = doc.id
        session.add(test_file)
        await session.commit()

        response = await drive_client.get(f"/api/v1/google-drive/files/{file_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["rag_status"] == "processing"
        assert data["rag_error"] is None

    @pytest.mark.asyncio
    async def test_get_file_not_found(self, drive_client: AsyncClient) -> None:
        """GET /files/{id} should return 404 for non-existent file."""
        response = await drive_client.get("/api/v1/google-drive/files/99999")

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

        with patch("sparkth.plugins.googledrive.routes.files.GoogleDriveClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.stream_download = _fake_stream
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_cls.return_value = mock_client

            response = await drive_client.get(f"/api/v1/google-drive/files/{test_file.id}/download")

        assert response.status_code == status.HTTP_200_OK
        assert response.content == b"file content"
        assert "attachment" in response.headers.get("content-disposition", "")

    @pytest.mark.asyncio
    async def test_download_google_doc_exports_pdf(
        self,
        drive_client: AsyncClient,
        test_oauth_token: DriveOAuthToken,
        mock_valid_access_token: None,
        session: AsyncSession,
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
        session.add(doc_file)
        await session.flush()
        await session.refresh(doc_file)

        from sparkth.plugins.googledrive.client import GoogleDriveClient as RealClient

        async def _fake_stream(*args: Any, **kwargs: Any) -> AsyncGenerator[bytes, None]:
            yield b"%PDF-1.4"

        with patch("sparkth.plugins.googledrive.routes.files.GoogleDriveClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.stream_download = _fake_stream
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_cls.return_value = mock_client
            mock_client_cls.EXPORT_MIME_MAP = RealClient.EXPORT_MIME_MAP

            response = await drive_client.get(f"/api/v1/google-drive/files/{doc_file.id}/download")

        assert response.status_code == status.HTTP_200_OK
        assert "application/pdf" in response.headers.get("content-type", "")
        assert "My Doc.pdf" in response.headers.get("content-disposition", "")

    @pytest.mark.asyncio
    async def test_download_file_not_found(
        self,
        drive_client: AsyncClient,
    ) -> None:
        """GET /files/{id}/download should return 404 for non-existent file."""
        response = await drive_client.get("/api/v1/google-drive/files/99999/download")

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

        with patch("sparkth.plugins.googledrive.routes.files.GoogleDriveClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.stream_download = _failing_stream
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_cls.return_value = mock_client

            with pytest.raises(RuntimeError, match="Drive API error"):
                await drive_client.get(f"/api/v1/google-drive/files/{test_file.id}/download")


class TestDeleteFile:
    @pytest.mark.asyncio
    async def test_delete_marks_file_as_deleted(
        self,
        drive_client: AsyncClient,
        test_file: DriveFile,
        session: AsyncSession,
    ) -> None:
        """DELETE /files/{id} should soft-delete locally; file remains in Google Drive."""
        response = await drive_client.delete(f"/api/v1/google-drive/files/{test_file.id}")

        assert response.status_code == status.HTTP_200_OK
        assert "removed" in response.json()["detail"].lower()

        await session.refresh(test_file)
        assert test_file.is_deleted is True
        assert test_file.deleted_at is not None

    @pytest.mark.asyncio
    async def test_deleted_file_no_longer_accessible(
        self,
        drive_client: AsyncClient,
        test_file: DriveFile,
        session: AsyncSession,
    ) -> None:
        """A soft-deleted file should return 404 on GET.

        The DELETE endpoint's soft-delete behaviour is covered by
        ``test_delete_marks_file_as_deleted``; here we verify that GET excludes
        an already-deleted file.
        """
        test_file.soft_delete()
        session.add(test_file)
        await session.flush()
        file_id = test_file.id

        response = await drive_client.get(f"/api/v1/google-drive/files/{file_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_file_not_found(self, drive_client: AsyncClient) -> None:
        """DELETE /files/{id} should return 404 for non-existent file."""
        response = await drive_client.delete("/api/v1/google-drive/files/99999")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_soft_deletes_linked_document(
        self,
        drive_client: AsyncClient,
        test_file: DriveFile,
        test_user: User,
        session: AsyncSession,
    ) -> None:
        """DELETE /files/{id} should soft-delete the file's linked Document."""
        document = Document(user_id=cast(int, test_user.id), name="linked.pdf")
        session.add(document)
        await session.commit()
        await session.refresh(document)
        test_file.document_id = document.id
        session.add(test_file)
        await session.commit()

        response = await drive_client.delete(f"/api/v1/google-drive/files/{test_file.id}")

        assert response.status_code == status.HTTP_200_OK
        await session.refresh(document)
        assert document.is_deleted is True


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
        response = await drive_client.get(f"/api/v1/google-drive/files/{test_file.id}/rag-status")

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
        session: AsyncSession,
        test_user: User,
    ) -> None:
        """GET /files/{id}/rag-status should return 'processing' while pipeline runs."""
        doc = Document(user_id=cast(int, test_user.id), name="test_document.pdf", status=DocumentStatus.PROCESSING)
        session.add(doc)
        await session.flush()
        await session.refresh(doc)
        assert test_file.id is not None
        file_id = test_file.id
        test_file.document_id = doc.id
        session.add(test_file)
        await session.commit()

        response = await drive_client.get(f"/api/v1/google-drive/files/{file_id}/rag-status")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["rag_status"] == "processing"

    @pytest.mark.asyncio
    async def test_returns_ready_status(
        self,
        drive_client: AsyncClient,
        test_file: DriveFile,
        session: AsyncSession,
        test_user: User,
    ) -> None:
        """GET /files/{id}/rag-status should return 'ready' when processing is complete."""
        doc = Document(user_id=cast(int, test_user.id), name="test_document.pdf", status=DocumentStatus.READY)
        session.add(doc)
        await session.flush()
        await session.refresh(doc)
        assert test_file.id is not None
        file_id = test_file.id
        test_file.document_id = doc.id
        session.add(test_file)
        await session.commit()

        response = await drive_client.get(f"/api/v1/google-drive/files/{file_id}/rag-status")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["rag_status"] == "ready"

    @pytest.mark.asyncio
    async def test_returns_failed_status(
        self,
        drive_client: AsyncClient,
        test_file: DriveFile,
        session: AsyncSession,
        test_user: User,
    ) -> None:
        """GET /files/{id}/rag-status should return 'failed' when processing errored."""
        doc = Document(user_id=cast(int, test_user.id), name="test_document.pdf", status=DocumentStatus.FAILED)
        session.add(doc)
        await session.flush()
        await session.refresh(doc)
        assert test_file.id is not None
        file_id = test_file.id
        test_file.document_id = doc.id
        session.add(test_file)
        await session.commit()

        response = await drive_client.get(f"/api/v1/google-drive/files/{file_id}/rag-status")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["rag_status"] == "failed"

    @pytest.mark.asyncio
    async def test_file_not_found(self, drive_client: AsyncClient) -> None:
        """GET /files/{id}/rag-status should return 404 for non-existent file."""
        response = await drive_client.get("/api/v1/google-drive/files/99999/rag-status")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_deleted_file_returns_404(
        self,
        drive_client: AsyncClient,
        test_file: DriveFile,
        session: AsyncSession,
    ) -> None:
        """GET /files/{id}/rag-status should return 404 for soft-deleted files."""
        test_file.soft_delete()
        session.add(test_file)
        await session.flush()

        response = await drive_client.get(f"/api/v1/google-drive/files/{test_file.id}/rag-status")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestGetFolderRagStatus:
    @pytest.mark.asyncio
    async def test_returns_statuses_for_all_files(
        self,
        drive_client: AsyncClient,
        test_folder: DriveFolder,
        test_file: DriveFile,
        session: AsyncSession,
        test_user: User,
    ) -> None:
        """GET /folders/{id}/rag-status should return rag_status for every file."""
        doc1 = Document(user_id=cast(int, test_user.id), name="test_document.pdf", status=DocumentStatus.READY)
        doc2 = Document(user_id=cast(int, test_user.id), name="slides.pdf", status=DocumentStatus.PROCESSING)
        session.add(doc1)
        session.add(doc2)
        await session.flush()
        await session.refresh(doc1)
        await session.refresh(doc2)
        assert test_folder.id is not None
        folder_id = test_folder.id
        test_file.document_id = doc1.id
        second_file = DriveFile(
            folder_id=folder_id,
            user_id=cast(int, test_user.id),
            drive_file_id="drive_file_second",
            name="slides.pdf",
            mime_type="application/pdf",
            size=512,
            last_synced_at=test_file.last_synced_at,
            document_id=doc2.id,
        )
        session.add(test_file)
        session.add(second_file)
        await session.commit()

        response = await drive_client.get(f"/api/v1/google-drive/folders/{folder_id}/rag-status")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["folder_id"] == folder_id
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
        response = await drive_client.get(f"/api/v1/google-drive/folders/{test_folder.id}/rag-status")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["folder_id"] == test_folder.id
        assert data["files"] == []

    @pytest.mark.asyncio
    async def test_folder_not_found(self, drive_client: AsyncClient) -> None:
        """GET /folders/{id}/rag-status should return 404 for non-existent folder."""
        response = await drive_client.get("/api/v1/google-drive/folders/99999/rag-status")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_excludes_deleted_files(
        self,
        drive_client: AsyncClient,
        test_folder: DriveFolder,
        test_file: DriveFile,
        session: AsyncSession,
        test_user: User,
    ) -> None:
        """GET /folders/{id}/rag-status should exclude soft-deleted files."""
        doc1 = Document(user_id=cast(int, test_user.id), name="test_document.pdf", status=DocumentStatus.READY)
        doc2 = Document(user_id=cast(int, test_user.id), name="deleted_doc.pdf", status=DocumentStatus.READY)
        session.add(doc1)
        session.add(doc2)
        await session.flush()
        await session.refresh(doc1)
        await session.refresh(doc2)
        assert test_folder.id is not None
        folder_id = test_folder.id
        test_file.document_id = doc1.id
        deleted_file = DriveFile(
            folder_id=folder_id,
            user_id=cast(int, test_user.id),
            drive_file_id="drive_file_deleted",
            name="deleted_doc.pdf",
            mime_type="application/pdf",
            size=1024,
            last_synced_at=test_file.last_synced_at,
            document_id=doc2.id,
        )
        deleted_file.soft_delete()
        session.add(test_file)
        session.add(deleted_file)
        await session.commit()

        response = await drive_client.get(f"/api/v1/google-drive/folders/{folder_id}/rag-status")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["files"]) == 1
        assert data["files"][0]["name"] == "test_document.pdf"


class TestRagErrorInResponse:
    @pytest.mark.asyncio
    async def test_failed_file_includes_rag_error(
        self,
        drive_client: AsyncClient,
        test_folder: DriveFolder,
        test_file: DriveFile,
        session: AsyncSession,
        test_user: User,
    ) -> None:
        """GET /folders/{id}/rag-status should include rag_error for failed files."""
        doc = Document(
            user_id=cast(int, test_user.id),
            name="test_document.pdf",
            status=DocumentStatus.FAILED,
            error="Download failed: 403 Forbidden",
        )
        session.add(doc)
        await session.flush()
        await session.refresh(doc)
        assert test_folder.id is not None
        folder_id = test_folder.id
        test_file.document_id = doc.id
        session.add(test_file)
        await session.commit()

        response = await drive_client.get(f"/api/v1/google-drive/folders/{folder_id}/rag-status")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        file_data = data["files"][0]
        assert file_data["rag_error"] == "Download failed: 403 Forbidden"

    @pytest.mark.asyncio
    async def test_non_failed_file_has_null_rag_error(
        self,
        drive_client: AsyncClient,
        test_folder: DriveFolder,
        test_file: DriveFile,
        session: AsyncSession,
        test_user: User,
    ) -> None:
        """GET /folders/{id}/rag-status should return null rag_error for non-failed files."""
        doc = Document(user_id=cast(int, test_user.id), name="test_document.pdf", status=DocumentStatus.READY)
        session.add(doc)
        await session.flush()
        await session.refresh(doc)
        assert test_folder.id is not None
        folder_id = test_folder.id
        test_file.document_id = doc.id
        session.add(test_file)
        await session.commit()

        response = await drive_client.get(f"/api/v1/google-drive/folders/{folder_id}/rag-status")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        file_data = data["files"][0]
        assert file_data["rag_error"] is None


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

        with patch("sparkth.plugins.googledrive.routes.files.GoogleDriveClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.browse.return_value = browse_result
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_cls.return_value = mock_client
            # Preserve FOLDER_MIME_TYPE so is_folder check works
            mock_client_cls.FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"

            response = await drive_client.get("/api/v1/google-drive/browse")

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
        with patch("sparkth.plugins.googledrive.routes.files.GoogleDriveClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.browse.return_value = {"files": []}
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_cls.return_value = mock_client

            response = await drive_client.get("/api/v1/google-drive/browse?folder_id=subfolder_123")

        assert response.status_code == status.HTTP_200_OK
        mock_client.browse.assert_called_once_with(folder_id="subfolder_123", page_token=None)


# ---------------------------------------------------------------------------
# Permission gates: records are checked at the owner's user scope
# ---------------------------------------------------------------------------

READ = "googledrive.read"
SYNC = "googledrive.sync"
DELETE = "googledrive.delete"
BASE = "/api/v1/google-drive"
UNKNOWN_ID = 999999

# method, path template ({folder} / {file}), permission, text the success body contains
BY_ID_ROUTES = [
    ("GET", "/folders/{folder}/files", READ, "owned.pdf"),
    ("GET", "/folders/{folder}/rag-status", READ, "owned.pdf"),
    ("GET", "/files/{file}", READ, "owned.pdf"),
    ("GET", "/files/{file}/rag-status", READ, "owned.pdf"),
    ("GET", "/files/{file}/download", READ, "file content"),
    ("POST", "/folders/{folder}/refresh", SYNC, "synced"),
    ("DELETE", "/files/{file}", DELETE, "removed"),
]
ROUTE_IDS = [f"{m} {p}" for m, p, _perm, _text in BY_ID_ROUTES]


class OwnedRecords:
    """A user's folder and file, as seeded for the gate tests."""

    def __init__(self, user_id: int, folder: DriveFolder, drive_file: DriveFile) -> None:
        self.user_id = user_id
        self.folder = folder
        self.file = drive_file

    def url(self, template: str) -> str:
        return BASE + template.format(folder=self.folder.id, file=self.file.id)


async def _seed_owned(session: AsyncSession, username: str) -> OwnedRecords:
    user = await make_user(session, username)
    user_id = cast(int, user.id)
    folder = DriveFolder(
        user_id=user_id,
        drive_folder_id=f"folder_{username}",
        drive_folder_name=f"folder of {username}",
        last_synced_at=datetime.now(timezone.utc),
        sync_status="synced",
    )
    session.add(folder)
    await session.flush()
    drive_file = DriveFile(
        folder_id=cast(int, folder.id),
        user_id=user_id,
        drive_file_id=f"file_{username}",
        name="owned.pdf",
        mime_type="application/pdf",
    )
    session.add(drive_file)
    await session.commit()
    return OwnedRecords(user_id, folder, drive_file)


async def _drop_caller_assignment(session: AsyncSession) -> None:
    await session.exec(delete(RoleAssignment))
    await session.commit()


@pytest.fixture
def drive_api() -> Iterator[AsyncMock]:
    """Stand in for Google: an empty folder listing, a one-chunk download, and no RAG background work."""

    async def _stream(*args: Any, **kwargs: Any) -> AsyncGenerator[bytes, None]:
        yield b"file content"

    client = AsyncMock()
    client.list_files.return_value = {"files": []}
    client.stream_download = _stream
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    with (
        patch("sparkth.plugins.googledrive.routes.folders.GoogleDriveClient", return_value=client),
        patch("sparkth.plugins.googledrive.routes.files.GoogleDriveClient", return_value=client),
        patch("sparkth.plugins.googledrive.routes.folders.process_folder_rag", new_callable=AsyncMock),
    ):
        yield client


@pytest.fixture
async def owner(session: AsyncSession, test_user: User) -> OwnedRecords:
    """Records of a second user; ``test_user`` is the caller."""
    return await _seed_owned(session, "driveowner")


@pytest.mark.usefixtures("drive_api", "mock_valid_access_token")
class TestByIdGate:
    @pytest.mark.parametrize(("method", "template", "permission", "text"), BY_ID_ROUTES, ids=ROUTE_IDS)
    async def test_own_record_with_the_default_role(
        self,
        drive_client: AsyncClient,
        test_folder: DriveFolder,
        test_file: DriveFile,
        method: str,
        template: str,
        permission: str,
        text: str,
    ) -> None:
        response = await drive_client.request(method, OwnedRecords(1, test_folder, test_file).url(template))

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.parametrize(("method", "template", "permission", "text"), BY_ID_ROUTES, ids=ROUTE_IDS)
    async def test_own_record_without_the_own_assignment_is_403(
        self,
        drive_client: AsyncClient,
        session: AsyncSession,
        test_folder: DriveFolder,
        test_file: DriveFile,
        method: str,
        template: str,
        permission: str,
        text: str,
    ) -> None:
        await _drop_caller_assignment(session)

        response = await drive_client.request(method, OwnedRecords(1, test_folder, test_file).url(template))

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.parametrize(("method", "template", "permission", "text"), BY_ID_ROUTES, ids=ROUTE_IDS)
    async def test_another_users_record_is_403_and_audited(
        self,
        drive_client: AsyncClient,
        owner: OwnedRecords,
        audit_events: AuditEventsFetcher,
        method: str,
        template: str,
        permission: str,
        text: str,
    ) -> None:
        response = await drive_client.request(method, owner.url(template))

        assert response.status_code == status.HTTP_403_FORBIDDEN
        (event,) = await audit_events()
        assert event.action == "denied"
        assert event.target_id == permission
        assert event.error_detail == f"scope=user:{owner.user_id}"

    @pytest.mark.parametrize(("method", "template", "permission", "text"), BY_ID_ROUTES, ids=ROUTE_IDS)
    @pytest.mark.parametrize("at_owner", [False, True], ids=["global", "owner"])
    async def test_grant_at_global_or_owner_reaches_it(
        self,
        drive_client: AsyncClient,
        session: AsyncSession,
        owner: OwnedRecords,
        method: str,
        template: str,
        permission: str,
        text: str,
        at_owner: bool,
    ) -> None:
        scope, object_id = (USER, str(owner.user_id)) if at_owner else (GLOBAL, None)
        await grant_permission_at_scope(session, 1, permission, scope, object_id)
        await session.commit()

        response = await drive_client.request(method, owner.url(template))

        assert response.status_code == status.HTTP_200_OK
        assert text in response.text

    @pytest.mark.parametrize(("method", "template", "permission", "text"), BY_ID_ROUTES, ids=ROUTE_IDS)
    async def test_grant_at_a_third_user_is_403(
        self,
        drive_client: AsyncClient,
        session: AsyncSession,
        owner: OwnedRecords,
        method: str,
        template: str,
        permission: str,
        text: str,
    ) -> None:
        third = await make_user(session, "drivethird")
        await grant_permission_at_scope(session, 1, permission, USER, str(third.id))
        await session.commit()

        response = await drive_client.request(method, owner.url(template))

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.parametrize(("method", "template", "permission", "text"), BY_ID_ROUTES, ids=ROUTE_IDS)
    async def test_unknown_id_is_404_without_a_denial_row(
        self,
        drive_client: AsyncClient,
        session: AsyncSession,
        audit_events: AuditEventsFetcher,
        method: str,
        template: str,
        permission: str,
        text: str,
    ) -> None:
        await _drop_caller_assignment(session)

        response = await drive_client.request(method, BASE + template.format(folder=UNKNOWN_ID, file=UNKNOWN_ID))

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert await audit_events() == []

    async def test_read_alone_cannot_sync_or_delete(
        self, drive_client: AsyncClient, session: AsyncSession, owner: OwnedRecords
    ) -> None:
        await grant_permission_at_scope(session, 1, READ, GLOBAL)
        await session.commit()

        refresh = await drive_client.post(owner.url("/folders/{folder}/refresh"))
        delete_response = await drive_client.delete(owner.url("/files/{file}"))

        assert (refresh.status_code, delete_response.status_code) == (403, 403)
        await session.refresh(owner.file)
        assert owner.file.is_deleted is False

    async def test_holder_delete_removes_the_owners_file(
        self, drive_client: AsyncClient, session: AsyncSession, owner: OwnedRecords
    ) -> None:
        await grant_permission_at_scope(session, 1, DELETE, GLOBAL)
        await session.commit()

        response = await drive_client.delete(owner.url("/files/{file}"))

        assert response.status_code == status.HTTP_200_OK
        await session.refresh(owner.file)
        assert owner.file.is_deleted is True

    async def test_holder_download_uses_the_owners_token(
        self, drive_client: AsyncClient, session: AsyncSession, owner: OwnedRecords
    ) -> None:
        await grant_permission_at_scope(session, 1, READ, GLOBAL)
        await session.commit()

        with patch(
            "sparkth.plugins.googledrive.routes.files.get_valid_access_token", return_value="owner_token"
        ) as get_token:
            response = await drive_client.get(owner.url("/files/{file}/download"))

        assert response.status_code == status.HTTP_200_OK
        assert get_token.call_args.args[1] == owner.user_id

    async def test_holder_refresh_uses_the_owners_token(
        self, drive_client: AsyncClient, session: AsyncSession, owner: OwnedRecords
    ) -> None:
        await grant_permission_at_scope(session, 1, SYNC, GLOBAL)
        await session.commit()

        with (
            patch(
                "sparkth.plugins.googledrive.routes.folders.get_valid_access_token", return_value="owner_token"
            ) as get_token,
            patch("sparkth.plugins.googledrive.routes.folders.process_folder_rag", new_callable=AsyncMock) as rag,
        ):
            response = await drive_client.post(owner.url("/folders/{folder}/refresh"))

        assert response.status_code == status.HTTP_200_OK
        assert get_token.call_args.args[1] == owner.user_id
        assert rag.call_args.args[1:] == (owner.user_id, "owner_token")


class TestListGate:
    async def test_list_shows_only_the_callers_even_with_a_global_grant(
        self, drive_client: AsyncClient, session: AsyncSession, test_folder: DriveFolder, owner: OwnedRecords
    ) -> None:
        await grant_permission_at_scope(session, 1, READ, GLOBAL)
        await session.commit()

        body = (await drive_client.get(f"{BASE}/folders")).json()

        assert [f["name"] for f in body["items"]] == ["Test Folder"]

    async def test_list_of_another_owner_needs_a_grant(self, drive_client: AsyncClient, owner: OwnedRecords) -> None:
        response = await drive_client.get(f"{BASE}/folders", params={"owner_id": owner.user_id})

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.parametrize("at_owner", [False, True], ids=["global", "owner"])
    async def test_list_of_another_owner_with_a_grant(
        self,
        drive_client: AsyncClient,
        session: AsyncSession,
        test_folder: DriveFolder,
        owner: OwnedRecords,
        at_owner: bool,
    ) -> None:
        scope, object_id = (USER, str(owner.user_id)) if at_owner else (GLOBAL, None)
        await grant_permission_at_scope(session, 1, READ, scope, object_id)
        await session.commit()

        body = (await drive_client.get(f"{BASE}/folders", params={"owner_id": owner.user_id})).json()

        assert [f["name"] for f in body["items"]] == ["folder of driveowner"]

    async def test_list_of_a_user_with_no_folders_is_empty(
        self, drive_client: AsyncClient, session: AsyncSession, test_user: User
    ) -> None:
        await grant_permission_at_scope(session, 1, READ, GLOBAL)
        await session.commit()

        body = (await drive_client.get(f"{BASE}/folders", params={"owner_id": UNKNOWN_ID})).json()

        assert body["items"] == []
        assert body["total"] == 0


class TestSyncGate:
    @pytest.mark.usefixtures("drive_api", "mock_valid_access_token")
    async def test_sync_without_the_own_assignment_is_403(
        self, drive_client: AsyncClient, session: AsyncSession
    ) -> None:
        await _drop_caller_assignment(session)

        response = await drive_client.post(f"{BASE}/folders/sync", json={"drive_folder_id": "any"})

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert (await session.exec(select(DriveFolder))).all() == []
