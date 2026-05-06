import json
from pathlib import Path
from typing import Any

from app.models.drive import DriveFile
from app.rag import constants


def get_asset(file_name: str, file_extension: str) -> str | dict[str, Any]:
    """Read a file from app/rag/assets and return its contents.

    Returns a str for .txt files and a dict for .json files.
    """
    ext = file_extension.lstrip(".")
    path = Path(__file__).parent / "assets" / f"{file_name}.{ext}"

    with path.open() as f:
        if ext == "txt":
            content = f.read()
        elif ext == "json":
            content = json.load(f)
        else:
            raise ValueError(f"Unsupported asset extension: {file_extension}")

    return content


def resolve_source_name(drive_file: DriveFile) -> str:
    """Return the source_name as stored in DocumentChunk."""
    filename = drive_file.name
    mime_type = drive_file.mime_type or ""
    if mime_type in constants.GOOGLE_NATIVE_MIMES and not filename.lower().endswith(".pdf"):
        filename = f"{filename}.pdf"
    return filename
