"""Exceptions for the Google Drive plugin."""


class GoogleDriveAPIError(RuntimeError):
    """Raised when a Google Drive API request fails."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"Google Drive API error ({status_code}): {message}")
