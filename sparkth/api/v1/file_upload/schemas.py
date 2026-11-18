"""Pydantic models for the file upload API."""

from pydantic import BaseModel


class UploadResponse(BaseModel):
    """The text read from an uploaded file."""

    filename: str | None
    length: int
    text: str
