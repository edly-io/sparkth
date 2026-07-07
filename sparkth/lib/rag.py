"""Public API for the RAG library.

All plugins and external modules import RAG functionality from here.
"""

from sparkth.rag.exceptions import (
    DocumentNotFoundError,
    RAGNotReadyError,
    RAGRetrievalError,
    ScannedPDFError,
    UnsupportedFileTypeError,
)
from sparkth.rag.formatting import format_document_chunks_as_llm_context
from sparkth.rag.ingestion import ingest_document
from sparkth.rag.retrieval import agentic_retrieve_context
from sparkth.rag.store import copy_document_chunk_links
from sparkth.rag.types import DocumentSection, RetrievedChunk
from sparkth.rag.utils import get_rag_ingested_document_structure

__all__ = [
    "DocumentNotFoundError",
    "RAGNotReadyError",
    "RAGRetrievalError",
    "ScannedPDFError",
    "UnsupportedFileTypeError",
    "format_document_chunks_as_llm_context",
    "ingest_document",
    "agentic_retrieve_context",
    "copy_document_chunk_links",
    "get_rag_ingested_document_structure",
    "DocumentSection",
    "RetrievedChunk",
]
