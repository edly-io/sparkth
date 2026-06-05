"""Public API for the RAG library.

All plugins and external modules import RAG functionality from here. Nothing
outside ``app/rag/`` should import from ``app.rag.*`` directly (see issue #398).
"""

import asyncio

from langchain_core.language_models import BaseChatModel

from app.lib.db import session_scope
from app.memory_profiler import profile_memory
from app.rag.enums import RagStatus  # noqa: F401 — re-exported in __all__
from app.rag.exceptions import (  # noqa: F401 — re-exported in __all__
    DriveFileNotFoundError,
    RAGNotReadyError,
    RAGRetrievalError,
    ScannedPDFError,
    UnsupportedFileTypeError,
)
from app.rag.ingestion.chunking import DocumentChunker
from app.rag.ingestion.extraction import check_extraction_eligibility, extract_to_markdown
from app.rag.retrieval import get_context_via_agent_with_isolated_session
from app.rag.retrieval.utils import _validate_files_ready
from app.rag.store import ChunkStoreService, store_and_link_chunks
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


async def ingest_document(
    user_id: int,
    owner_file_id: int,
    file_bytes: bytes,
    filename: str,
) -> IngestionResult:
    """Ingest a document's bytes into the RAG store.

    Pipeline: eligibility check -> extract -> chunk -> store (with cross-file
    content-hash dedup) -> link chunks to *owner_file_id*. Opens and commits its
    own database session.

    Args:
        user_id: Owner of the chunks (row-level scope).
        owner_file_id: File id recorded in the chunk-link table.
        file_bytes: Raw file content.
        filename: Original filename (drives extension dispatch).

    Returns:
        IngestionResult with new/reused chunk counts. A file that yields no
        chunks returns (0, 0).

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
                new_count, reused_count = await store_and_link_chunks(session, user_id, owner_file_id, chunks, store)
            await session.commit()

    return IngestionResult(new_chunks=new_count, reused_chunks=reused_count)


async def agentic_retrieve_context(
    user_id: int,
    file_ids: list[int],
    query: str,
    llm: BaseChatModel,
) -> list[RetrievedChunk]:
    """Retrieve relevant document chunks for a query across the given files.

    Validates that every file is owned by the user and READY (raising otherwise),
    then uses agentic section retrieval per file and returns a flat list of
    RetrievedChunk. Opens its own database sessions.

    Args:
        user_id: Owner of the files (row-level scope).
        file_ids: Files to search. All must exist and be READY.
        query: The user's natural-language query.
        llm: LangChain chat model used by the retrieval agent.

    Returns:
        Flat list of RetrievedChunk across all files (empty if no matches).

    Raises:
        DriveFileNotFoundError: a file is missing or not owned by the user.
        RAGNotReadyError: a file exists but is not READY.
        RAGRetrievalError: retrieval failed.
    """
    if not file_ids:
        return []

    async with session_scope() as session:
        await _validate_files_ready(session, user_id, file_ids)

    tasks = [get_context_via_agent_with_isolated_session(user_id, fid, query, llm) for fid in file_ids]
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
