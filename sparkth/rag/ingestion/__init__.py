"""RAG ingestion module — extraction, chunking, and storage of documents."""

import asyncio

from sparkth.lib.audit import record_event, record_event_now, scrub_error_detail
from sparkth.lib.audit.events import (
    AuditChange,
    AuditOutcome,
    AuditTarget,
    RAGDocumentIngestedAuditEvent,
)
from sparkth.lib.db import session_scope
from sparkth.lib.log import get_logger
from sparkth.memory_profiler import profile_memory
from sparkth.rag.exceptions import ScannedPDFError, UnsupportedFileTypeError
from sparkth.rag.ingestion.chunking import DocumentChunker
from sparkth.rag.ingestion.extraction import check_extraction_eligibility, extract_to_markdown
from sparkth.rag.store import ChunkStoreService, store_and_link_chunks
from sparkth.rag.types import IngestionResult

logger = get_logger(__name__)


def _ingested_event(
    document_id: int,
    outcome: AuditOutcome,
    *,
    change: AuditChange | None = None,
    error_detail: str | None = None,
) -> RAGDocumentIngestedAuditEvent:
    return RAGDocumentIngestedAuditEvent(
        outcome=outcome,
        target=AuditTarget(type="document", id=str(document_id)),
        change=change,
        error_detail=error_detail,
    )


def _success_change(filename: str, result: IngestionResult) -> AuditChange:
    return AuditChange(
        new={
            "filename": filename,
            "new_chunks": result.new_chunks,
            "reused_chunks": result.reused_chunks,
        }
    )


async def ingest_document(
    filename: str,
    file_bytes: bytes,
    document_id: int,
) -> IngestionResult:
    """Ingest a document's bytes into the RAG store.

    Pipeline: eligibility check -> extract -> chunk -> store (with cross-document
    content-hash dedup) -> link chunks to *document_id*. Opens and commits its
    own database session.

    Audited as a ``rag.document_ingested`` event. A success is recorded in the
    same transaction as the chunk write (fail-closed, so unrecordable content
    cannot enter the corpus). A failure is recorded, in its own transaction
    before the error propagates, for the two eligibility/extraction errors this
    function declares below; any other error (a parse failure inside an
    extractor, a chunker error, a database error from the chunk write)
    propagates without an audit record. Nothing entered the corpus in those
    cases, so the trail stays accurate about the corpus itself, but it is not a
    complete log of attempts.

    Args:
        document_id: Document.id recorded in the chunk-link table.
        file_bytes: Raw file content.
        filename: Original filename (drives extension dispatch).

    Returns:
        IngestionResult with new/reused chunk counts.

    Raises:
        UnsupportedFileTypeError: type the extractors cannot handle.
        ScannedPDFError: PDF appears scanned/image-only.
    """
    try:
        check_extraction_eligibility(filename)

        async with profile_memory("pipeline_total", file=filename):
            async with profile_memory("extraction", file=filename, size_bytes=len(file_bytes)):
                extraction_result = await asyncio.to_thread(extract_to_markdown, file_bytes, filename)

            async with profile_memory("chunking", file=filename, markdown_chars=len(extraction_result.markdown)):
                chunks = await asyncio.to_thread(DocumentChunker().chunk, extraction_result)

            if not chunks:
                # Nothing was stored, so there is no store transaction to
                # join; the attempt is still recorded, in its own transaction.
                result = IngestionResult(new_chunks=0, reused_chunks=0)
                await record_event_now(
                    _ingested_event(document_id, AuditOutcome.SUCCESS, change=_success_change(filename, result))
                )
                return result

            store = ChunkStoreService()
            async with session_scope() as session:
                async with profile_memory("store_and_link", file=filename, chunks=len(chunks)):
                    new_count, reused_count = await store_and_link_chunks(session, document_id, chunks, store)
                result = IngestionResult(new_chunks=new_count, reused_chunks=reused_count)
                await record_event(
                    session,
                    _ingested_event(document_id, AuditOutcome.SUCCESS, change=_success_change(filename, result)),
                )
                await session.commit()
    except (UnsupportedFileTypeError, ScannedPDFError) as exc:
        logger.warning("Ingestion of '%s' (document_id=%d) failed: %s", filename, document_id, exc)
        await record_event_now(_ingested_event(document_id, AuditOutcome.FAILURE, error_detail=scrub_error_detail(exc)))
        raise

    return result
