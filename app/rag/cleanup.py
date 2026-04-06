"""RAG cleanup: remove chunks orphaned by soft-deleted Drive files."""

import asyncio
import logging

from sqlalchemy import delete
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import async_engine
from app.models.drive import DriveFile  # noqa: TCH001
from app.rag.models import DocumentChunk, DriveFileChunkLink

logger = logging.getLogger(__name__)


async def cleanup_deleted_files() -> None:
    """Delete chunks orphaned by soft-deleted Drive files.

    A chunk is only deleted when every Drive file that references it
    has been soft-deleted (i.e. shared chunks are preserved).

    This is a system-wide background job: it operates across all users
    intentionally, as orphan cleanup is not scoped per user.
    """
    async with AsyncSession(async_engine, expire_on_commit=False) as session:
        deleted_ids_result = await session.execute(
            select(DriveFile.id).where(col(DriveFile.is_deleted) == True)  # noqa: E712
        )
        deleted_file_ids = [row[0] for row in deleted_ids_result.all()]

        if not deleted_file_ids:
            logger.info("No deleted files found. Nothing to clean up.")
            return

        logger.info("Found %d deleted Drive files to process.", len(deleted_file_ids))

        # Chunks linked to deleted files
        candidate_result = await session.execute(
            select(DriveFileChunkLink.chunk_id).where(
                DriveFileChunkLink.drive_file_id.in_(deleted_file_ids)  # type: ignore[attr-defined]
            )
        )
        candidate_chunk_ids = {row[0] for row in candidate_result.all()}

        if not candidate_chunk_ids:
            logger.info("No chunks linked to deleted files.")
            return

        # Chunks still referenced by at least one live file
        alive_result = await session.execute(
            select(DriveFileChunkLink.chunk_id)
            .join(DriveFile, DriveFileChunkLink.drive_file_id == DriveFile.id)  # type: ignore[arg-type]
            .where(
                DriveFileChunkLink.chunk_id.in_(candidate_chunk_ids),  # type: ignore[attr-defined]
                col(DriveFile.is_deleted) == False,  # noqa: E712
            )
        )
        alive_chunk_ids = {row[0] for row in alive_result.all()}

        orphan_chunk_ids = candidate_chunk_ids - alive_chunk_ids

        if not orphan_chunk_ids:
            logger.info("No orphaned chunks. All candidates still referenced by live files.")
            return

        logger.info("%d orphaned chunks will be deleted.", len(orphan_chunk_ids))

        # Remove ALL bridge-table links for deleted files (not just orphan links)
        # so the FK constraint on DriveFile.id is satisfied before hard-deletion.
        await session.execute(
            delete(DriveFileChunkLink).where(
                DriveFileChunkLink.drive_file_id.in_(deleted_file_ids)  # type: ignore[attr-defined]
            )
        )

        # Delete orphaned chunks
        await session.execute(
            delete(DocumentChunk).where(
                DocumentChunk.id.in_(orphan_chunk_ids)  # type: ignore[union-attr]
            )
        )

        # Hard-delete the soft-deleted DriveFile rows
        await session.execute(
            delete(DriveFile).where(
                DriveFile.id.in_(deleted_file_ids)  # type: ignore[union-attr]
            )
        )

        await session.commit()
        logger.info(
            "Cleanup complete. Deleted %d orphaned chunks and %d drive file records.",
            len(orphan_chunk_ids),
            len(deleted_file_ids),
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
    asyncio.run(cleanup_deleted_files())
