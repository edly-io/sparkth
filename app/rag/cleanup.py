"""RAG cleanup: remove chunks orphaned by soft-deleted Drive files."""

import asyncio

from sqlalchemy import delete
from sqlmodel import col, select

from app.lib.db import session_scope
from app.lib.log import configure_logging, get_logger
from app.models.drive import DriveFile  # noqa: TCH001
from app.rag.models import DocumentChunk, DriveFileChunkLink

logger = get_logger(__name__)


async def cleanup_deleted_files() -> None:
    """Delete chunks orphaned by soft-deleted Drive files and duplicate files.

    A chunk is only deleted when every Drive file that references it
    has been soft-deleted (i.e. shared chunks are preserved).

    Duplicate drive_file records (with no chunks) are always hard-deleted
    when marked as soft-deleted.

    This is a system-wide background job: it operates across all users
    intentionally, as orphan cleanup is not scoped per user.
    """
    async with session_scope() as session:
        deleted_ids_result = await session.scalars(
            select(DriveFile.id).where(col(DriveFile.is_deleted) == True)  # noqa: E712
        )
        deleted_file_ids = list(deleted_ids_result.all())

        if not deleted_file_ids:
            logger.info("No deleted files found. Nothing to clean up.")
            return

        logger.info("Found %d deleted Drive files to process.", len(deleted_file_ids))

        # Chunks linked to deleted files
        candidate_result = await session.scalars(
            select(DriveFileChunkLink.chunk_id).where(col(DriveFileChunkLink.drive_file_id).in_(deleted_file_ids))
        )
        candidate_chunk_ids = set(candidate_result.all())

        orphan_chunk_ids = set()

        if candidate_chunk_ids:
            # Chunks still referenced by at least one live file
            alive_result = await session.scalars(
                select(DriveFileChunkLink.chunk_id)
                .join(DriveFile, col(DriveFileChunkLink.drive_file_id) == col(DriveFile.id))
                .where(
                    col(DriveFileChunkLink.chunk_id).in_(candidate_chunk_ids),
                    col(DriveFile.is_deleted) == False,  # noqa: E712
                )
            )
            alive_chunk_ids = set(alive_result.all())

            orphan_chunk_ids = candidate_chunk_ids - alive_chunk_ids

        if orphan_chunk_ids:
            logger.info("%d orphaned chunks will be deleted.", len(orphan_chunk_ids))
        else:
            logger.info("No orphaned chunks found.")

        # Remove ALL bridge-table links for deleted files (not just orphan links)
        # so the FK constraint on DriveFile.id is satisfied before hard-deletion.
        await session.execute(
            delete(DriveFileChunkLink).where(col(DriveFileChunkLink.drive_file_id).in_(deleted_file_ids))
        )

        # Delete orphaned chunks
        if orphan_chunk_ids:
            await session.execute(delete(DocumentChunk).where(col(DocumentChunk.id).in_(orphan_chunk_ids)))

        # Hard-delete the soft-deleted DriveFile rows (including duplicates with no chunks)
        await session.execute(delete(DriveFile).where(col(DriveFile.id).in_(deleted_file_ids)))

        await session.commit()
        logger.info(
            "Cleanup complete. Deleted %d orphaned chunks and %d drive file records.",
            len(orphan_chunk_ids),
            len(deleted_file_ids),
        )


if __name__ == "__main__":
    configure_logging()
    asyncio.run(cleanup_deleted_files())
