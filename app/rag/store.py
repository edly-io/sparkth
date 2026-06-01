"""Document chunk storage service."""

from typing import Any

from sqlalchemy import and_, delete, or_
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.logger import get_logger
from app.memory_profiler import profile_memory
from app.rag.db_models import DocumentChunk
from app.rag.types import ChunkInput, SimilarityResult

# Re-export for backwards-compatibility with modules that import from store
__all__ = ["ChunkInput", "SimilarityResult", "VectorStoreService"]

logger = get_logger(__name__)


class VectorStoreService:
    """Service for storing and retrieving document chunks."""

    async def store_chunks(
        self,
        session: AsyncSession,
        user_id: int,
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

        batch_size = get_settings().RAG_STORE_BATCH_SIZE
        source = chunks[0].source_name
        all_ids: list[int] = []

        for batch_start in range(0, len(chunks), batch_size):
            batch = chunks[batch_start : batch_start + batch_size]

            batch_rows: list[DocumentChunk] = []
            for chunk in batch:
                row = DocumentChunk(
                    user_id=user_id,
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

            async with profile_memory("vectorstore_write", source=source, n_rows=len(batch_rows)):
                await session.flush()

            batch_ids = [row.id for row in batch_rows if row.id is not None]
            session.expunge_all()
            del batch_rows
            all_ids.extend(batch_ids)

        logger.info(
            "Stored %d chunks for user_id=%d, source='%s'",
            len(all_ids),
            user_id,
            source,
        )
        return all_ids

    async def fetch_chunks_by_sections(
        self,
        session: AsyncSession,
        user_id: int,
        source_name: str,
        section_keys: list[dict[str, str | None]],
        limit: int = 50,
    ) -> list[SimilarityResult]:
        """Fetch chunks for specific section keys in document order (by id).

        Matches exact (chapter, section, subsection) tuples — NULL-safe.
        Returns SimilarityResult with similarity=1.0 (no vector scoring).
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
        chunks = result.all()
        return [SimilarityResult(chunk=chunk, similarity=1.0) for chunk in chunks]

    async def delete_by_source(
        self,
        session: AsyncSession,
        user_id: int,
        source_name: str,
    ) -> int:
        """Delete all chunks for a given source document. Returns count deleted.

        Note: this method flushes but does not commit. The caller is
        responsible for committing (or rolling back) the transaction.
        """
        stmt = (
            delete(DocumentChunk)
            .where(col(DocumentChunk.user_id) == user_id)
            .where(col(DocumentChunk.source_name) == source_name)
        )
        result = await session.execute(stmt)
        await session.flush()
        count: int = result.rowcount  # type: ignore[attr-defined]
        logger.info("Deleted %d chunks for user_id=%d, source='%s'", count, user_id, source_name)
        return count

    async def get_sources(
        self,
        session: AsyncSession,
        user_id: int,
    ) -> list[str]:
        """List all distinct source names for a user."""
        stmt = (
            select(DocumentChunk.source_name)
            .where(col(DocumentChunk.user_id) == user_id)
            .distinct()
            .order_by(col(DocumentChunk.source_name))
        )
        result = await session.exec(stmt)
        return list(result.all())
