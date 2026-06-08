"""Public API for the RAG library.

All plugins and external modules import RAG functionality from here. Nothing
outside ``app/rag/`` should import from ``app.rag.*`` directly (see issue #398).
"""

from app.lib.db import session_scope
from app.rag.exceptions import DocumentNotFoundError as DocumentNotFoundError
from app.rag.exceptions import DriveFileNotFoundError as DriveFileNotFoundError  # backward-compat alias
from app.rag.exceptions import RAGNotReadyError as RAGNotReadyError
from app.rag.exceptions import RAGRetrievalError as RAGRetrievalError
from app.rag.exceptions import ScannedPDFError as ScannedPDFError
from app.rag.exceptions import UnsupportedFileTypeError as UnsupportedFileTypeError
from app.rag.ingestion import ingest_document as ingest_document
from app.rag.retrieval import agentic_retrieve_context as agentic_retrieve_context
from app.rag.store import _copy_document_chunk_links
from app.rag.types import IngestionResult as IngestionResult
from app.rag.types import RetrievedChunk as RetrievedChunk


async def copy_chunk_links(source_document_id: int, target_document_id: int) -> None:
    """Copy all chunk links from source_document_id to target_document_id.

    Used by plugins to handle duplicate-content files: if a file has identical
    content to an already-ingested document, copy the links instead of re-ingesting.
    Opens and commits its own database session.

    Args:
        source_document_id: Document.id to copy links from (must be READY).
        target_document_id: Document.id to copy links to.
    """
    async with session_scope() as session:
        await _copy_document_chunk_links(session, source_document_id, target_document_id)
        await session.commit()
