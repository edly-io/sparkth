"""Unit tests for GoogleDriveClient."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core_plugins.googledrive.client import GoogleDriveClient


def _mock_aiohttp_response(status: int = 200, json_data: dict | None = None, content: bytes = b""):
    """Create a mock aiohttp response."""
    response = AsyncMock()
    response.status = status
    response.json = AsyncMock(return_value=json_data or {})
    response.text = AsyncMock(return_value=str(json_data or ""))
    response.read = AsyncMock(return_value=content)
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)
    return response


def _mock_session():
    """Create a mock aiohttp.ClientSession."""
    session = MagicMock()
    session.closed = False
    session.close = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    return session


class TestGoogleDriveClientListFiles:
    @pytest.mark.asyncio
    async def test_list_files_root(self) -> None:
        """List files in root folder."""
        files_data = {
            "files": [
                {"id": "f1", "name": "doc.pdf", "mimeType": "application/pdf", "size": "1024"},
            ],
            "nextPageToken": None,
        }
        response = _mock_aiohttp_response(json_data=files_data)
        session = _mock_session()
        session.request.return_value = response

        client = GoogleDriveClient("fake_token")
        client.session = session

        result = await client.list_files()

        assert result == files_data
        session.request.assert_called_once()
        call_args = session.request.call_args
        assert call_args[0][0] == "GET"
        assert "files" in call_args[0][1]
        params = call_args[1]["params"]
        assert "'root' in parents" in params["q"]
        assert "trashed = false" in params["q"]

    @pytest.mark.asyncio
    async def test_list_files_with_folder_id(self) -> None:
        """List files in a specific folder."""
        response = _mock_aiohttp_response(json_data={"files": []})
        session = _mock_session()
        session.request.return_value = response

        client = GoogleDriveClient("fake_token")
        client.session = session

        await client.list_files(folder_id="folder123")

        params = session.request.call_args[1]["params"]
        assert "'folder123' in parents" in params["q"]

    @pytest.mark.asyncio
    async def test_list_files_with_query(self) -> None:
        """List files with additional query filter."""
        response = _mock_aiohttp_response(json_data={"files": []})
        session = _mock_session()
        session.request.return_value = response

        client = GoogleDriveClient("fake_token")
        client.session = session

        await client.list_files(query="mimeType = 'application/pdf'")

        params = session.request.call_args[1]["params"]
        assert "mimeType = 'application/pdf'" in params["q"]

    @pytest.mark.asyncio
    async def test_list_files_with_pagination(self) -> None:
        """List files with page token."""
        response = _mock_aiohttp_response(json_data={"files": []})
        session = _mock_session()
        session.request.return_value = response

        client = GoogleDriveClient("fake_token")
        client.session = session

        await client.list_files(page_token="next_page_token_123")

        params = session.request.call_args[1]["params"]
        assert params["pageToken"] == "next_page_token_123"


class TestGoogleDriveClientDownload:
    @pytest.mark.asyncio
    async def test_download_regular_file(self) -> None:
        """Download a regular (non-Google Docs) file."""
        content = b"file content bytes"
        response = _mock_aiohttp_response(status=200, content=content)
        session = _mock_session()
        session.get.return_value = response

        client = GoogleDriveClient("fake_token")
        client.session = session

        result = await client.download_file("file_id_123", mime_type="application/pdf")

        assert result == content
        session.get.assert_called_once()
        call_args = session.get.call_args
        assert "file_id_123" in call_args[0][0]
        assert call_args[1]["params"] == {"alt": "media"}

    @pytest.mark.asyncio
    async def test_download_google_doc_exports_as_pdf(self) -> None:
        """Google Docs files should be exported as PDF."""
        pdf_content = b"%PDF-1.4 fake pdf"
        export_response = _mock_aiohttp_response(status=200, content=pdf_content)
        session = _mock_session()
        session.get.return_value = export_response

        client = GoogleDriveClient("fake_token")
        client.session = session

        result = await client.download_file(
            "doc_id",
            mime_type="application/vnd.google-apps.document",
        )

        assert result == pdf_content
        call_args = session.get.call_args
        assert "/export" in call_args[0][0]
        assert call_args[1]["params"]["mimeType"] == "application/pdf"

    @pytest.mark.asyncio
    async def test_download_google_spreadsheet_exports_as_pdf(self) -> None:
        """Google Sheets should be exported as PDF."""
        pdf_content = b"%PDF-1.4 spreadsheet"
        export_response = _mock_aiohttp_response(status=200, content=pdf_content)
        session = _mock_session()
        session.get.return_value = export_response

        client = GoogleDriveClient("fake_token")
        client.session = session

        result = await client.download_file(
            "sheet_id",
            mime_type="application/vnd.google-apps.spreadsheet",
        )

        assert result == pdf_content

    @pytest.mark.asyncio
    async def test_download_error_raises_runtime_error(self) -> None:
        """Download errors should raise RuntimeError."""
        error_response = _mock_aiohttp_response(status=403)
        error_response.text = AsyncMock(return_value="Access denied")
        session = _mock_session()
        session.get.return_value = error_response

        client = GoogleDriveClient("fake_token")
        client.session = session

        with pytest.raises(RuntimeError, match="Download error"):
            await client.download_file("file_id")

    @pytest.mark.asyncio
    async def test_download_without_session_raises(self) -> None:
        """Calling download without session should raise RuntimeError."""
        client = GoogleDriveClient("fake_token")

        with pytest.raises(RuntimeError, match="not initialized"):
            await client.download_file("file_id")


class TestGoogleDriveClientUpload:
    @pytest.mark.asyncio
    async def test_upload_file(self) -> None:
        """Upload a file with multipart request."""
        upload_result = {
            "id": "new_file_id",
            "name": "uploaded.pdf",
            "mimeType": "application/pdf",
            "size": "2048",
        }
        response = _mock_aiohttp_response(status=200, json_data=upload_result)
        session = _mock_session()
        session.post.return_value = response

        client = GoogleDriveClient("fake_token")
        client.session = session

        result = await client.upload_file(
            name="uploaded.pdf",
            content=b"pdf content",
            mime_type="application/pdf",
            folder_id="parent_folder",
        )

        assert result["id"] == "new_file_id"
        session.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_error_raises(self) -> None:
        """Upload errors should raise."""
        response = _mock_aiohttp_response(status=500)
        response.text = AsyncMock(return_value="Internal Server Error")
        session = _mock_session()
        session.post.return_value = response

        client = GoogleDriveClient("fake_token")
        client.session = session

        with pytest.raises(Exception, match="Upload error"):
            await client.upload_file("file.txt", b"data", "text/plain")


class TestGoogleDriveClientMutations:
    @pytest.mark.asyncio
    async def test_rename_file(self) -> None:
        """Rename a file sends PATCH with new name."""
        response = _mock_aiohttp_response(json_data={"id": "f1", "name": "renamed.pdf"})
        session = _mock_session()
        session.request.return_value = response

        client = GoogleDriveClient("fake_token")
        client.session = session

        result = await client.rename_file("f1", "renamed.pdf")

        assert result["name"] == "renamed.pdf"
        call_args = session.request.call_args
        assert call_args[0][0] == "PATCH"
        assert call_args[1]["json"] == {"name": "renamed.pdf"}

    @pytest.mark.asyncio
    async def test_delete_file(self) -> None:
        """Delete a file sends DELETE request."""
        response = _mock_aiohttp_response(status=204)
        session = _mock_session()
        session.request.return_value = response

        client = GoogleDriveClient("fake_token")
        client.session = session

        result = await client.delete_file("f1")

        assert result is True
        call_args = session.request.call_args
        assert call_args[0][0] == "DELETE"

    @pytest.mark.asyncio
    async def test_create_folder(self) -> None:
        """Create a folder sends POST with folder MIME type."""
        response = _mock_aiohttp_response(json_data={"id": "new_folder_id", "name": "New Folder"})
        session = _mock_session()
        session.request.return_value = response

        client = GoogleDriveClient("fake_token")
        client.session = session

        result = await client.create_folder("New Folder", parent_id="parent123")

        assert result["id"] == "new_folder_id"
        call_args = session.request.call_args
        json_body = call_args[1]["json"]
        assert json_body["name"] == "New Folder"
        assert json_body["mimeType"] == GoogleDriveClient.FOLDER_MIME_TYPE
        assert json_body["parents"] == ["parent123"]


class TestGoogleDriveClientRequestErrors:
    @pytest.mark.asyncio
    async def test_request_raises_runtime_error_on_4xx(self) -> None:
        """API errors should raise RuntimeError, not bare Exception."""
        response = _mock_aiohttp_response(status=403)
        response.text = AsyncMock(return_value="Forbidden")
        session = _mock_session()
        session.request.return_value = response

        client = GoogleDriveClient("fake_token")
        client.session = session

        with pytest.raises(RuntimeError, match="Google Drive API error.*403"):
            await client.get_file("f1")

    @pytest.mark.asyncio
    async def test_request_without_session_raises(self) -> None:
        """Calling _request without session should raise RuntimeError."""
        client = GoogleDriveClient("fake_token")

        with pytest.raises(RuntimeError, match="not initialized"):
            await client.get_file("f1")


class TestGoogleDriveClientContextManager:
    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        """Client works as async context manager."""
        with patch("aiohttp.ClientSession") as mock_cls:
            mock_session = MagicMock()
            mock_session.closed = False
            mock_session.close = AsyncMock()
            mock_cls.return_value = mock_session

            async with GoogleDriveClient("token") as client:
                assert client.session is mock_session

            mock_session.close.assert_awaited_once()


class TestGoogleDriveClientSearch:
    @pytest.mark.asyncio
    async def test_search_files(self) -> None:
        """Search files by name."""
        search_result = {"files": [{"id": "f1", "name": "report.pdf"}]}
        response = _mock_aiohttp_response(json_data=search_result)
        session = _mock_session()
        session.request.return_value = response

        client = GoogleDriveClient("fake_token")
        client.session = session

        result = await client.search_files("report")

        assert len(result) == 1
        assert result[0]["name"] == "report.pdf"
        params = session.request.call_args[1]["params"]
        assert "name contains 'report'" in params["q"]
