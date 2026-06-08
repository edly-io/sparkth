"""Public API for the RAG library.

All plugins and external modules import RAG functionality from here. Nothing
outside ``app/rag/`` should import from ``app.rag.*`` directly.
"""

from app.rag.enums import RagStatus  # noqa: F401 — re-exported in __all__
from app.rag.exceptions import (  # noqa: F401 — re-exported in __all__
    DriveFileNotFoundError,
    RAGNotReadyError,
    RAGRetrievalError,
    ScannedPDFError,
    UnsupportedFileTypeError,
)
from app.rag.ingestion import ingest_document
from app.rag.retrieval import agentic_retrieve_context
from app.rag.types import IngestionResult, RetrievedChunk  # noqa: F401 — re-exported in __all__

__all__ = [
    "DriveFileNotFoundError",
    "IngestionResult",
    "RAGNotReadyError",
    "RAGRetrievalError",
    "RagStatus",
    "RetrievedChunk",
    "ScannedPDFError",
    "UnsupportedFileTypeError",
    "agentic_retrieve_context",
    "ingest_document",
]
