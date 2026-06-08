"""Public API for the RAG library.

All plugins and external modules import RAG functionality from here. Nothing
outside ``app/rag/`` should import from ``app.rag.*`` directly (see issue #398).
"""

import asyncio

from langchain_core.language_models import BaseChatModel

from app.lib.db import session_scope
from app.memory_profiler import profile_memory
from app.rag.exceptions import DocumentNotFoundError as DocumentNotFoundError
from app.rag.exceptions import DriveFileNotFoundError as DriveFileNotFoundError  # backward-compat alias
from app.rag.exceptions import RAGNotReadyError as RAGNotReadyError
from app.rag.exceptions import RAGRetrievalError as RAGRetrievalError
from app.rag.exceptions import ScannedPDFError as ScannedPDFError
from app.rag.exceptions import UnsupportedFileTypeError as UnsupportedFileTypeError
from app.rag.ingestion.chunking import DocumentChunker
from app.rag.ingestion.extraction import check_extraction_eligibility, extract_to_markdown
from app.rag.retrieval import get_context_via_agent_with_isolated_session
from app.rag.retrieval.utils import validate_files_ready
from app.rag.store import ChunkStoreService, _copy_document_chunk_links, store_and_link_chunks
from app.rag.types import IngestionResult as IngestionResult
from app.rag.types import RetrievedChunk as RetrievedChunk


async def ingest_document(
    user_id: int,
    document_id: int,
    file_bytes: bytes,
    filename: str,
) -> IngestionResult:
    """Ingest a document's bytes into the RAG store.

    Pipeline: eligibility check -> extract -> chunk -> store (with cross-document
    content-hash dedup) -> link chunks to *document_id*. Opens and commits its
    own database session.

    Args:
        user_id: Owner of the chunks (row-level scope).
        document_id: Document.id recorded in the chunk-link table.
        file_bytes: Raw file content.
        filename: Original filename (drives extension dispatch).

    Returns:
        IngestionResult with new/reused chunk counts.

    Raises:
        UnsupportedFileTypeError: type the extractors cannot handle.
        ScannedPDFError: PDF appears scanned/image-only.
    """
    check_extraction_eligibility(filename)

    async with profile_memory("pipeline_total", file=filename):
        async with profile_memory("extraction", file=filename, size_bytes=len(file_bytes)):
            extraction_result = await asyncio.to_thread(extract_to_markdown, file_bytes, filename)

        async with profile_memory("chunking", file=filename, markdown_chars=len(extraction_result.markdown)):
            chunks = await asyncio.to_thread(DocumentChunker().chunk, extraction_result)

        if not chunks:
            return IngestionResult(new_chunks=0, reused_chunks=0)

        store = ChunkStoreService()
        async with session_scope() as session:
            async with profile_memory("store_and_link", file=filename, chunks=len(chunks)):
                new_count, reused_count = await store_and_link_chunks(session, user_id, document_id, chunks, store)
            await session.commit()

    return IngestionResult(new_chunks=new_count, reused_chunks=reused_count)


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


async def agentic_retrieve_context(
    user_id: int,
    document_ids: list[int],
    query: str,
    llm: BaseChatModel,
) -> list[RetrievedChunk]:
    """Retrieve relevant document chunks for a query across the given documents.

    Validates that every document is owned by the user and READY (raising
    otherwise), then uses agentic section retrieval per document and returns a
    flat list of RetrievedChunk. Opens its own database sessions.

    Args:
        user_id: Owner of the documents (row-level scope).
        document_ids: Documents to search. All must exist and be READY.
        query: The user's natural-language query.
        llm: LangChain chat model used by the retrieval agent.

    Returns:
        Flat list of RetrievedChunk across all documents (empty if no matches).

    Raises:
        DocumentNotFoundError: a document is missing or not owned by the user.
        RAGNotReadyError: a document exists but is not READY.
        RAGRetrievalError: retrieval failed.
    """
    if not document_ids:
        return []

    async with session_scope() as session:
        await validate_files_ready(session, user_id, document_ids)

    tasks = [get_context_via_agent_with_isolated_session(user_id, did, query, llm) for did in document_ids]
    contexts = await asyncio.gather(*tasks)

    return [
        RetrievedChunk(
            source_name=sr.chunk.source_name,
            chapter=sr.chunk.chapter,
            section=sr.chunk.section,
            subsection=sr.chunk.subsection,
            content=sr.chunk.content,
        )
        for ctx in contexts
        for sr in ctx.chunks
    ]
