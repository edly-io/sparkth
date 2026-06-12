"""RAG database storage service — shared by ingestion and retrieval.

``ChunkStoreService`` is the single point of contact between the RAG pipeline
and the database. Ingestion uses it to persist and deduplicate chunks;
retrieval uses it to fetch chunks by section.
"""

import hashlib
from typing import Any, cast

from sqlalchemy import and_, delete, or_
from sqlalchemy.engine import CursorResult
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.lib.documents import Document
from app.lib.log import get_logger
from app.memory_profiler import profile_memory
from app.rag.config import get_rag_settings
from app.rag.models import DocumentChunk, DocumentChunkLink
from app.rag.types import Chunk, ChunkInput

logger = get_logger(__name__)


class ChunkStoreService:
    """Service for storing and retrieving document chunks."""

    async def store_chunks(
        self,
        session: AsyncSession,
        chunks: list[ChunkInput],
    ) -> list[int]:
        """Persist chunks in configurable sub-batches (no embedding).

        Processes RAG_STORE_BATCH_SIZE chunks per iteration, expunging batch
        objects from session identity map after each flush to prevent
        accumulating ORM objects in memory.

        Returns: list of created DocumentChunk IDs.
        Note: flushes after each batch but does not commit. The caller commits.
        """
        if not chunks:
            return []

        batch_size = get_rag_settings().RAG_STORE_BATCH_SIZE
        source = chunks[0].source_name
        all_ids: list[int] = []

        for batch_start in range(0, len(chunks), batch_size):
            batch = chunks[batch_start : batch_start + batch_size]

            batch_rows: list[DocumentChunk] = []
            for chunk in batch:
                row = DocumentChunk(
                    source_name=chunk.source_name,
                    content=chunk.content,
                    chunk_content_hash=chunk.chunk_content_hash,
                    chapter=chunk.chapter,
                    section=chunk.section,
                    subsection=chunk.subsection,
                    token_count=chunk.token_count,
                )
                session.add(row)
                batch_rows.append(row)

            async with profile_memory("chunkstore_write", source=source, n_rows=len(batch_rows)):
                await session.flush()

            batch_ids = [row.id for row in batch_rows if row.id is not None]
            session.expunge_all()
            del batch_rows
            all_ids.extend(batch_ids)

        logger.info("Stored %d chunks for source='%s'", len(all_ids), source)
        return all_ids

    async def fetch_chunks_by_sections(
        self,
        session: AsyncSession,
        user_id: int,
        source_name: str,
        section_keys: list[dict[str, str | None]],
        limit: int = 50,
    ) -> list[DocumentChunk]:
        """Fetch chunks for specific section keys in document order (by id).

        Matches exact (chapter, section, subsection) tuples — NULL-safe.
        """
        if not section_keys:
            return []

        # Following is a guard for the case where too many sections are being selected.
        # Adding this as a comment for now, will make implementation in future.
        # section_keys = section_keys[:MAX_SECTIONS]

        def _key_condition(key: dict[str, str | None]) -> Any:
            chapter = key.get("chapter")
            section = key.get("section")
            subsection = key.get("subsection")
            return and_(
                col(DocumentChunk.chapter) == chapter if chapter is not None else col(DocumentChunk.chapter).is_(None),
                col(DocumentChunk.section) == section if section is not None else col(DocumentChunk.section).is_(None),
                col(DocumentChunk.subsection) == subsection
                if subsection is not None
                else col(DocumentChunk.subsection).is_(None),
            )

        stmt = (
            select(DocumentChunk)
            .where(
                col(DocumentChunk.user_id) == user_id,
                col(DocumentChunk.source_name) == source_name,
                or_(*[_key_condition(k) for k in section_keys]),
            )
            .order_by(col(DocumentChunk.id))
            .limit(limit)
        )

        result = await session.exec(stmt)
        return list(result.all())

    async def delete_by_source(
        self,
        session: AsyncSession,
        source_name: str,
    ) -> int:
        """Delete all chunks for a given source document. Returns count deleted.

        Note: this method flushes but does not commit. The caller is
        responsible for committing (or rolling back) the transaction.
        """
        stmt = delete(DocumentChunk).where(col(DocumentChunk.source_name) == source_name)
        result = await session.execute(stmt)
        await session.flush()
        count: int = cast(CursorResult[Any], result).rowcount
        logger.info("Deleted %d chunks for source='%s'", count, source_name)
        return count

    async def get_sources(
        self,
        session: AsyncSession,
    ) -> list[str]:
        """List all distinct source names."""
        stmt = select(DocumentChunk.source_name).distinct().order_by(col(DocumentChunk.source_name))
        result = await session.scalars(stmt)
        return list(result.all())


async def _create_missing_links(session: AsyncSession, document_id: int, chunk_ids: set[int]) -> None:
    """Insert bridge-table links for chunk_ids not already linked to document_id."""
    already_linked = await session.scalars(
        select(DocumentChunkLink.chunk_id).where(
            col(DocumentChunkLink.document_id) == document_id,
        )
    )
    existing_ids = set(already_linked.all())
    new_links = [DocumentChunkLink(document_id=document_id, chunk_id=cid) for cid in chunk_ids - existing_ids]
    if new_links:
        session.add_all(new_links)
        await session.flush()


async def copy_document_chunk_links(
    session: AsyncSession,
    source_document_id: int,
    target_document_id: int,
) -> None:
    """Copy all chunk links from source_document_id to target_document_id."""
    source_chunk_ids = await session.scalars(
        select(DocumentChunkLink.chunk_id).where(
            col(DocumentChunkLink.document_id) == source_document_id,
        )
    )
    chunk_ids = set(source_chunk_ids.all())
    await _create_missing_links(session, target_document_id, chunk_ids)


async def store_and_link_chunks(
    session: AsyncSession,
    document_id: int,
    chunks: list[Chunk],
    store: ChunkStoreService,
) -> tuple[int, int]:
    """Store new chunks, reuse existing ones, and create bridge-table links.

    Returns (new_count, reused_count).
    """
    chunk_hashes = [hashlib.sha256(c.content.encode()).hexdigest() for c in chunks]

    active_doc_subq = (
        select(DocumentChunkLink.chunk_id)
        .join(Document, col(Document.id) == col(DocumentChunkLink.document_id))
        .where(
            col(DocumentChunkLink.chunk_id) == col(DocumentChunk.id),
            col(Document.is_deleted) == False,  # noqa: E712
        )
        .exists()
    )
    # Batch-lookup which chunk hashes already exist, excluding chunks that are
    # only linked to soft-deleted documents (they must be re-stored for the new document).
    existing_rows = await session.exec(
        select(DocumentChunk.id, DocumentChunk.chunk_content_hash).where(
            col(DocumentChunk.chunk_content_hash).in_(chunk_hashes),
            active_doc_subq,
        )
    )
    existing_hash_to_id: dict[str, int] = {
        row[1]: row[0] for row in existing_rows.all() if row[0] is not None and row[1] is not None
    }

    new_chunk_inputs: list[ChunkInput] = []
    reused_chunk_ids: list[int] = []

    for chunk, chunk_hash in zip(chunks, chunk_hashes):
        if chunk_hash in existing_hash_to_id:
            reused_chunk_ids.append(existing_hash_to_id[chunk_hash])
            logger.debug("Duplicate chunk (hash=%s) — reusing existing.", chunk_hash[:12])
        else:
            new_chunk_inputs.append(
                ChunkInput(
                    content=chunk.content,
                    source_name=chunk.metadata.source_name,
                    chapter=chunk.metadata.chapter,
                    section=chunk.metadata.section,
                    subsection=chunk.metadata.subsection,
                    chunk_content_hash=chunk_hash,
                )
            )

    new_ids = await store.store_chunks(session, new_chunk_inputs)

    all_chunk_ids: set[int] = set(new_ids) | set(reused_chunk_ids)
    await _create_missing_links(session, document_id, all_chunk_ids)

    return len(new_chunk_inputs), len(reused_chunk_ids)
