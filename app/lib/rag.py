"""Public API for the RAG library.

All plugins and external modules import RAG functionality from here.
"""

from app.rag.exceptions import (
    DocumentNotFoundError,
    RAGNotReadyError,
    RAGRetrievalError,
    ScannedPDFError,
    UnsupportedFileTypeError,
)
from app.rag.ingestion import ingest_document
from app.rag.retrieval import agentic_retrieve_context
from app.rag.store import copy_document_chunk_links
from app.rag.types import DocumentSection, RetrievedChunk
from app.rag.utils import get_rag_ingested_document_structure

__all__ = [
    "DocumentNotFoundError",
    "RAGNotReadyError",
    "RAGRetrievalError",
    "ScannedPDFError",
    "UnsupportedFileTypeError",
    "ingest_document",
    "agentic_retrieve_context",
    "copy_document_chunk_links",
    "get_rag_ingested_document_structure",
    "DocumentSection",
    "RetrievedChunk",
]
