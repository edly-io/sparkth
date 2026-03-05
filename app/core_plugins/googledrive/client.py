"""Google Drive API client."""

from types import TracebackType
from typing import Any, Optional, Type

import aiohttp


class GoogleDriveClient:
    """Async client for Google Drive API."""

    BASE_URL = "https://www.googleapis.com/drive/v3"
    UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3"
    FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"

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

    def _headers(self) -> dict[str, str]:
        """Get authorization headers."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }

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
                error_text = await response.text()
                raise RuntimeError(f"Google Drive API error ({response.status}): {error_text}")

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
        if not self.session:
            raise RuntimeError("Client session not initialized.")

        # Google Docs native types cannot be downloaded directly — export them
        if mime_type and mime_type in self.EXPORT_MIME_MAP:
            return await self.export_file(file_id, self.EXPORT_MIME_MAP[mime_type])

        url = f"{self.BASE_URL}/files/{file_id}"
        params = {"alt": "media"}

        async with self.session.get(url, params=params, headers=self._headers()) as response:
            if response.status >= 400:
                error_text = await response.text()
                raise RuntimeError(f"Download error ({response.status}): {error_text}")
            return await response.read()

    async def export_file(self, file_id: str, export_mime_type: str) -> bytes:
        """Export a Google Docs editor file to the given MIME type."""
        if not self.session:
            raise RuntimeError("Client session not initialized.")

        url = f"{self.BASE_URL}/files/{file_id}/export"
        params = {"mimeType": export_mime_type}

        async with self.session.get(url, params=params, headers=self._headers()) as response:
            if response.status >= 400:
                error_text = await response.text()
                raise RuntimeError(f"Export error ({response.status}): {error_text}")
            return await response.read()

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

        import json as json_module

        metadata: dict[str, Any] = {"name": name}
        if folder_id:
            metadata["parents"] = [folder_id]

        boundary = "sparkth_boundary"
        body_parts = [
            f"--{boundary}",
            "Content-Type: application/json; charset=UTF-8",
            "",
            json_module.dumps(metadata),
            f"--{boundary}",
            f"Content-Type: {mime_type}",
            "",
        ]
        body_prefix = "\r\n".join(body_parts).encode("utf-8") + b"\r\n"
        body_suffix = f"\r\n--{boundary}--".encode("utf-8")
        body = body_prefix + content + body_suffix

        headers = {
            **self._headers(),
            "Content-Type": f"multipart/related; boundary={boundary}",
        }

        url = f"{self.UPLOAD_URL}/files?uploadType=multipart&fields=id,name,mimeType,size,md5Checksum,modifiedTime"

        async with self.session.post(url, data=body, headers=headers) as response:
            if response.status >= 400:
                error_text = await response.text()
                raise Exception(f"Upload error ({response.status}): {error_text}")
            result: dict[str, Any] = await response.json()
            return result

    async def update_file(self, file_id: str, content: bytes, mime_type: str) -> dict[str, Any]:
        """Update file content."""
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
                error_text = await response.text()
                raise Exception(f"Update error ({response.status}): {error_text}")
            result: dict[str, Any] = await response.json()
            return result

    async def rename_file(self, file_id: str, new_name: str) -> dict[str, Any]:
        """Rename a file or folder."""
        return await self._request(
            "PATCH",
            f"{self.BASE_URL}/files/{file_id}",
            json={"name": new_name},
            headers={"Content-Type": "application/json"},
        )

    async def delete_file(self, file_id: str) -> bool:
        """Delete a file or folder (moves to trash)."""
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
        q = f"name contains '{query}'"
        result = await self.list_files(folder_id=folder_id, query=q)
        files: list[dict[str, Any]] = result.get("files", [])
        return files
