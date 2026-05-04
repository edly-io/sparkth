import json
from pathlib import Path
from typing import Any

from app.models.drive import DriveFile
from app.rag import constants


def get_asset(file_name: str, file_extension: str) -> str | dict[str, Any]:
    """Read a file from app/rag/assets and return its contents.

    Returns a str for .txt files and a dict for .json files.
    """
    rag_assets_dir = Path(__file__).parent / "assets"
    path = rag_assets_dir / f"{file_name}.{file_extension.lstrip('.')}"

    with open(path) as f:
        if file_extension.lstrip(".") == "txt":
            content = f.read()
        elif file_extension.lstrip(".") == "json":
            content = json.load(f)

    return content


def resolve_source_name(drive_file: DriveFile) -> str:
    """Return the source_name as stored in DocumentChunk."""
    filename = drive_file.name
    mime_type = drive_file.mime_type or ""
    if mime_type in constants.GOOGLE_NATIVE_MIMES and not filename.lower().endswith(".pdf"):
        filename = f"{filename}.pdf"
    return filename
