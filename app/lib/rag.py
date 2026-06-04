"""Public API for the RAG library.

All plugins and external modules import RAG functionality from here. Nothing
outside ``app/rag/`` should import from ``app.rag.*`` directly (see issue #398).
"""

from app.rag.enums import RagStatus
from app.rag.exceptions import (
    FileTypeNotAllowedError,
    ScannedPDFError,
    UnsupportedFileTypeError,
)
from app.rag.ingestion import IngestionResult, ingest_document

__all__ = [
    "FileTypeNotAllowedError",
    "IngestionResult",
    "RagStatus",
    "ScannedPDFError",
    "UnsupportedFileTypeError",
    "ingest_document",
]
