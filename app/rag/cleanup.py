"""RAG cleanup: remove chunks orphaned by soft-deleted Documents."""

import asyncio

from sqlalchemy import delete
from sqlmodel import col, select

from app.lib.db import session_scope
from app.lib.documents import Document
from app.lib.log import configure_logging, get_logger
from app.rag.models import DocumentChunk, DocumentChunkLink

logger = get_logger(__name__)


async def cleanup_deleted_documents() -> None:
    """Delete chunks orphaned by soft-deleted Documents.

    A chunk is only deleted when every Document that references it
    has been soft-deleted (i.e. shared chunks are preserved).

    Cleanup does NOT hard-delete Document rows — that is the responsibility
    of the plugin that owns the document via soft_delete_document().

    This is a system-wide background job: it operates across all users
    intentionally, as orphan cleanup is not scoped per user.
    """
    async with session_scope() as session:
        deleted_ids_result = await session.scalars(
            select(Document.id).where(col(Document.is_deleted) == True)  # noqa: E712
        )
        deleted_doc_ids = list(deleted_ids_result.all())

        if not deleted_doc_ids:
            logger.info("No deleted documents found. Nothing to clean up.")
            return

        logger.info("Found %d deleted Documents to process.", len(deleted_doc_ids))

        candidate_result = await session.scalars(
            select(DocumentChunkLink.chunk_id).where(col(DocumentChunkLink.document_id).in_(deleted_doc_ids))
        )
        candidate_chunk_ids = set(candidate_result.all())

        orphan_chunk_ids: set[int] = set()

        if candidate_chunk_ids:
            alive_result = await session.scalars(
                select(DocumentChunkLink.chunk_id)
                .join(Document, col(DocumentChunkLink.document_id) == col(Document.id))
                .where(
                    col(DocumentChunkLink.chunk_id).in_(candidate_chunk_ids),
                    col(Document.is_deleted) == False,  # noqa: E712
                )
            )
            alive_chunk_ids = set(alive_result.all())
            orphan_chunk_ids = candidate_chunk_ids - alive_chunk_ids

        if orphan_chunk_ids:
            logger.info("%d orphaned chunks will be deleted.", len(orphan_chunk_ids))
        else:
            logger.info("No orphaned chunks found.")

        await session.execute(delete(DocumentChunkLink).where(col(DocumentChunkLink.document_id).in_(deleted_doc_ids)))

        if orphan_chunk_ids:
            await session.execute(delete(DocumentChunk).where(col(DocumentChunk.id).in_(orphan_chunk_ids)))

        await session.commit()
        logger.info(
            "Cleanup complete. Deleted %d orphaned chunks.",
            len(orphan_chunk_ids),
        )


if __name__ == "__main__":
    configure_logging()
    asyncio.run(cleanup_deleted_documents())
