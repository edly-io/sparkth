"""RAG document ingestion: the public entry point and its pipeline helpers."""

import hashlib

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.lib.log import get_logger
from app.models.drive import DriveFile
from app.rag.models import DocumentChunk, DriveFileChunkLink
from app.rag.store import ChunkStoreService
from app.rag.types import Chunk, ChunkInput

logger = get_logger(__name__)


async def _create_missing_links(session: AsyncSession, drive_file_id: int, chunk_ids: set[int]) -> None:
    """Insert bridge-table links for chunk_ids not already linked to drive_file_id."""
    already_linked = await session.scalars(
        select(DriveFileChunkLink.chunk_id).where(
            col(DriveFileChunkLink.drive_file_id) == drive_file_id,
        )
    )
    existing_ids = set(already_linked.all())
    new_links = [DriveFileChunkLink(drive_file_id=drive_file_id, chunk_id=cid) for cid in chunk_ids - existing_ids]
    if new_links:
        session.add_all(new_links)
        await session.flush()


async def _store_and_link_chunks(
    session: AsyncSession,
    user_id: int,
    drive_file_id: int,
    chunks: list[Chunk],
    store: ChunkStoreService,
) -> tuple[int, int]:
    """Store new chunks, reuse existing ones, and create bridge-table links.

    Returns (new_count, reused_count).
    """
    chunk_hashes = [hashlib.sha256(c.content.encode()).hexdigest() for c in chunks]

    # Batch-lookup which chunk hashes already exist, excluding chunks that are
    # only linked to soft-deleted files (they must be re-stored for the new file).
    active_file_subq = (
        select(DriveFileChunkLink.chunk_id)
        .join(DriveFile, col(DriveFile.id) == col(DriveFileChunkLink.drive_file_id))
        .where(
            col(DriveFileChunkLink.chunk_id) == col(DocumentChunk.id),
            col(DriveFile.is_deleted) == False,  # noqa: E712
        )
        .exists()
    )
    existing_rows = await session.exec(
        select(DocumentChunk.id, DocumentChunk.chunk_content_hash).where(
            col(DocumentChunk.user_id) == user_id,
            col(DocumentChunk.chunk_content_hash).in_(chunk_hashes),
            active_file_subq,
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

    new_ids = await store.store_chunks(session, user_id, new_chunk_inputs)

    all_chunk_ids: set[int] = set(new_ids) | set(reused_chunk_ids)
    await _create_missing_links(session, drive_file_id, all_chunk_ids)

    return len(new_chunk_inputs), len(reused_chunk_ids)
