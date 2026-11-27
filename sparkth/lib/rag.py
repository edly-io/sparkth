"""Public API for the RAG library.

All plugins and external modules import RAG functionality from here.
"""

from sparkth.rag.document_access import bind_readable_document_ids, get_readable_document
from sparkth.rag.exceptions import (
    DocumentNotFoundError,
    RAGNotReadyError,
    RAGRetrievalError,
    ScannedPDFError,
    UnsupportedFileTypeError,
)
from sparkth.rag.formatting import format_document_chunks_as_llm_context
from sparkth.rag.ingestion import ingest_document
from sparkth.rag.mcp.tools import (
    get_chunk_stats,
    get_document_metadata,
    get_document_structure,
    list_document_sections,
    search_section_by_keyword,
)
from sparkth.rag.retrieval import agentic_retrieve_context, get_section_chunks
from sparkth.rag.schemas import DocumentSections, SectionRef, SectionSelection
from sparkth.rag.store import copy_document_chunk_links
from sparkth.rag.types import DocumentSection, RetrievedChunk

__all__ = [
    "bind_readable_document_ids",
    "get_readable_document",
    "DocumentNotFoundError",
    "RAGNotReadyError",
    "RAGRetrievalError",
    "ScannedPDFError",
    "UnsupportedFileTypeError",
    "format_document_chunks_as_llm_context",
    "ingest_document",
    "agentic_retrieve_context",
    "get_section_chunks",
    "copy_document_chunk_links",
    "get_chunk_stats",
    "get_document_metadata",
    "get_document_structure",
    "list_document_sections",
    "search_section_by_keyword",
    "DocumentSection",
    "DocumentSections",
    "SectionRef",
    "SectionSelection",
    "RetrievedChunk",
]
