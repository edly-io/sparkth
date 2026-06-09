"""RAG utility functions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


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
