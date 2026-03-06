"""Google Drive API client."""

import json
import re
from types import TracebackType
from typing import Any, Optional, Type

import aiohttp
from aiohttp import MultipartWriter


class GoogleDriveAPIError(RuntimeError):
    """Raised when a Google Drive API request fails."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"Google Drive API error ({status_code}): {message}")


class GoogleDriveClient:
    """Async client for Google Drive API."""

    BASE_URL = "https://www.googleapis.com/drive/v3"
    UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3"
    FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
    _DRIVE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")

    def __init__(self, access_token: str):
        self.access_token = access_token
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self) -> "GoogleDriveClient":
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(
        self,
        _exc_type: Optional[Type[BaseException]],
        _exc_val: Optional[BaseException],
        _exc_tb: Optional[TracebackType],
    ) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the client session."""
        if self.session and not self.session.closed:
            await self.session.close()

    @classmethod
    def _validate_id(cls, drive_id: str) -> str:
        """Validate a Google Drive file/folder ID to prevent path traversal."""
        if not cls._DRIVE_ID_PATTERN.match(drive_id):
            raise ValueError(f"Invalid Drive ID: {drive_id}")
        return drive_id  # validated, safe to use

    def _headers(self) -> dict[str, str]:
        """Get authorization headers."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }

    @staticmethod
    async def _parse_error(response: aiohttp.ClientResponse) -> str:
        """Extract a human-readable error message from a Google API error response."""
        text = await response.text()
        try:
            data = json.loads(text)
            if isinstance(data, dict) and "error" in data:
                error = data["error"]
                if isinstance(error, dict) and "message" in error:
                    return str(error["message"])
            return text
        except (json.JSONDecodeError, KeyError, TypeError):
            return text

    async def _request(
        self,
        method: str,
        url: str,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        data: Optional[bytes] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """Make an HTTP request to Google Drive API."""
        if not self.session:
            raise RuntimeError("Client session not initialized. Use async with.")

        request_headers = self._headers()
        if headers:
            request_headers.update(headers)

        async with self.session.request(
            method, url, params=params, json=json, data=data, headers=request_headers
        ) as response:
            if response.status >= 400:
                error_message = await self._parse_error(response)
                raise GoogleDriveAPIError(response.status, error_message)

            if response.status == 204:
                return {}

            result: dict[str, Any] = await response.json()
            return result

    async def list_files(
        self,
        folder_id: Optional[str] = None,
        page_token: Optional[str] = None,
        page_size: int = 100,
        query: Optional[str] = None,
    ) -> dict[str, Any]:
        """List files in Google Drive."""
        params: dict[str, Any] = {
            "pageSize": page_size,
            "fields": "nextPageToken, files(id, name, mimeType, size, md5Checksum, modifiedTime, parents)",
        }

        q_parts = ["trashed = false"]
        if folder_id:
            self._validate_id(folder_id)
            q_parts.append(f"'{folder_id}' in parents")
        else:
            q_parts.append("'root' in parents")
        if query:
            q_parts.append(query)

        params["q"] = " and ".join(q_parts)

        if page_token:
            params["pageToken"] = page_token

        return await self._request("GET", f"{self.BASE_URL}/files", params=params)

    async def get_file(self, file_id: str) -> dict[str, Any]:
        """Get file metadata."""
        self._validate_id(file_id)
        params = {"fields": "id, name, mimeType, size, md5Checksum, modifiedTime, parents"}
        return await self._request("GET", f"{self.BASE_URL}/files/{file_id}", params=params)

    # Google Docs editor types that must be exported rather than downloaded
    EXPORT_MIME_MAP: dict[str, str] = {
        "application/vnd.google-apps.document": "application/pdf",
        "application/vnd.google-apps.spreadsheet": "application/pdf",
        "application/vnd.google-apps.presentation": "application/pdf",
        "application/vnd.google-apps.drawing": "application/pdf",
    }

    async def download_file(self, file_id: str, mime_type: str | None = None) -> bytes:
        """Download file content. Auto-exports Google Docs editor files as PDF."""
        chunks = []
        async for chunk in self.stream_download(file_id, mime_type=mime_type):
            chunks.append(chunk)
        return b"".join(chunks)

    async def stream_download(
        self,
        file_id: str,
        mime_type: str | None = None,
        chunk_size: int = 64 * 1024,
    ) -> Any:
        """Stream file content in chunks. Auto-exports Google Docs editor files as PDF."""
        self._validate_id(file_id)
        if not self.session:
            raise RuntimeError("Client session not initialized.")

        # Google Docs native types cannot be downloaded directly — export them
        if mime_type and mime_type in self.EXPORT_MIME_MAP:
            url = f"{self.BASE_URL}/files/{file_id}/export"
            params: dict[str, str] = {"mimeType": self.EXPORT_MIME_MAP[mime_type]}
        else:
            url = f"{self.BASE_URL}/files/{file_id}"
            params = {"alt": "media"}

        async with self.session.get(url, params=params, headers=self._headers()) as response:
            if response.status >= 400:
                error_message = await self._parse_error(response)
                raise GoogleDriveAPIError(response.status, error_message)
            async for chunk in response.content.iter_chunked(chunk_size):
                yield chunk

    async def list_folders(self, parent_id: Optional[str] = None) -> list[dict[str, Any]]:
        """List folders in Google Drive."""
        result = await self.list_files(folder_id=parent_id, query=f"mimeType = '{self.FOLDER_MIME_TYPE}'")
        files: list[dict[str, Any]] = result.get("files", [])
        return files

    async def get_folder(self, folder_id: str) -> dict[str, Any]:
        """Get folder metadata."""
        return await self.get_file(folder_id)

    async def create_folder(self, name: str, parent_id: Optional[str] = None) -> dict[str, Any]:
        """Create a new folder in Google Drive."""
        metadata: dict[str, Any] = {
            "name": name,
            "mimeType": self.FOLDER_MIME_TYPE,
        }
        if parent_id:
            self._validate_id(parent_id)
            metadata["parents"] = [parent_id]

        return await self._request(
            "POST",
            f"{self.BASE_URL}/files",
            json=metadata,
            headers={"Content-Type": "application/json"},
        )

    async def upload_file(
        self,
        name: str,
        content: bytes,
        mime_type: str,
        folder_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Upload a file to Google Drive using multipart upload."""
        if not self.session:
            raise RuntimeError("Client session not initialized.")

        metadata: dict[str, Any] = {"name": name}
        if folder_id:
            self._validate_id(folder_id)
            metadata["parents"] = [folder_id]

        writer = MultipartWriter("related")
        metadata_payload = json.dumps(metadata).encode("utf-8")
        metadata_part = writer.append(metadata_payload)
        metadata_part.headers[aiohttp.hdrs.CONTENT_TYPE] = "application/json; charset=UTF-8"
        file_part = writer.append(content)
        file_part.headers[aiohttp.hdrs.CONTENT_TYPE] = mime_type

        headers = {
            **self._headers(),
            "Content-Type": f"multipart/related; boundary={writer.boundary}",
        }

        url = f"{self.UPLOAD_URL}/files?uploadType=multipart&fields=id,name,mimeType,size,md5Checksum,modifiedTime"

        async with self.session.post(url, data=writer, headers=headers) as response:
            if response.status >= 400:
                error_message = await self._parse_error(response)
                raise GoogleDriveAPIError(response.status, error_message)
            result: dict[str, Any] = await response.json()
            return result

    async def update_file(self, file_id: str, content: bytes, mime_type: str) -> dict[str, Any]:
        """Update file content."""
        self._validate_id(file_id)
        if not self.session:
            raise RuntimeError("Client session not initialized.")

        url = (
            f"{self.UPLOAD_URL}/files/{file_id}?uploadType=media&fields=id,name,mimeType,size,md5Checksum,modifiedTime"
        )
        headers = {
            **self._headers(),
            "Content-Type": mime_type,
        }

        async with self.session.patch(url, data=content, headers=headers) as response:
            if response.status >= 400:
                error_message = await self._parse_error(response)
                raise GoogleDriveAPIError(response.status, error_message)
            result: dict[str, Any] = await response.json()
            return result

    async def rename_file(self, file_id: str, new_name: str) -> dict[str, Any]:
        """Rename a file or folder."""
        self._validate_id(file_id)
        return await self._request(
            "PATCH",
            f"{self.BASE_URL}/files/{file_id}",
            json={"name": new_name},
            headers={"Content-Type": "application/json"},
        )

    async def delete_file(self, file_id: str) -> bool:
        """Delete a file or folder (moves to trash)."""
        self._validate_id(file_id)
        await self._request("DELETE", f"{self.BASE_URL}/files/{file_id}")
        return True

    async def browse(
        self,
        folder_id: Optional[str] = None,
        page_token: Optional[str] = None,
    ) -> dict[str, Any]:
        """Browse Drive folder contents (both files and folders)."""
        return await self.list_files(folder_id=folder_id, page_token=page_token)

    async def search_files(self, query: str, folder_id: Optional[str] = None) -> list[dict[str, Any]]:
        """Search for files by name."""
        # Escape single quotes and backslashes to prevent query injection
        sanitized = query.replace("\\", "\\\\").replace("'", "\\'")
        q = f"name contains '{sanitized}'"
        result = await self.list_files(folder_id=folder_id, query=q)
        files: list[dict[str, Any]] = result.get("files", [])
        return files
