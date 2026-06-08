"""RAG ingestion module — extraction, chunking, and storage of documents."""

import asyncio

from app.lib.db import session_scope
from app.memory_profiler import profile_memory
from app.rag.ingestion.chunking import DocumentChunker
from app.rag.ingestion.extraction import check_extraction_eligibility, extract_to_markdown
from app.rag.store import ChunkStoreService, store_and_link_chunks
from app.rag.types import IngestionResult

__all__ = ["ingest_document"]


async def ingest_document(
    filename: str,
    file_bytes: bytes,
    owner_file_id: int,
    user_id: int,
) -> IngestionResult:
    """Ingest a document's bytes into the RAG store.

    Pipeline: eligibility check -> extract -> chunk -> store (with cross-file
    content-hash dedup) -> link chunks to *owner_file_id*. Opens and commits its
    own database session.

    Args:
        filename: Original filename (drives extension dispatch).
        file_bytes: Raw file content.
        owner_file_id: File id recorded in the chunk-link table.
        user_id: Owner of the chunks (row-level scope).

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
