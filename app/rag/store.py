"""Vector store service for storing and retrieving document chunks."""

from dataclasses import dataclass

from sqlalchemy import delete, literal
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.logger import get_logger
from app.rag.embeddings import BaseEmbeddingProvider
from app.rag.memory_profiler import profile_memory
from app.rag.models import DocumentChunk

logger = get_logger(__name__)


@dataclass
class ChunkInput:
    """Input data for a single chunk to be embedded and stored.

    This is a standalone type so the store module compiles without
    the chunking PR (#202). Once that PR merges, callers can map
    ``Chunk`` / ``ChunkMetadata`` to ``ChunkInput`` trivially.
    """

    content: str
    source_name: str
    chapter: str | None = None
    section: str | None = None
    subsection: str | None = None
    token_count: int | None = None
    chunk_content_hash: str | None = None


@dataclass
class SimilarityResult:
    """A chunk together with its cosine similarity score."""

    chunk: DocumentChunk
    similarity: float


class VectorStoreService:
    """Service for storing and retrieving document chunks with vector embeddings."""

    async def store_chunks(
        self,
        session: AsyncSession,
        user_id: int,
        chunks: list[ChunkInput],
        provider: BaseEmbeddingProvider,
    ) -> list[DocumentChunk]:
        """Embed and persist chunks in configurable sub-batches.

        Processes RAG_STORE_BATCH_SIZE chunks per iteration so that embedding
        tensors and ORM row objects are released after each flush rather than
        accumulating for the entire document.

        Returns: created DocumentChunk rows (with IDs populated).
        Note: flushes after each batch but does not commit. The caller commits.
        """
        if not chunks:
            return []

        batch_size = get_settings().RAG_STORE_BATCH_SIZE
        source = chunks[0].source_name
        all_rows: list[DocumentChunk] = []

        for batch_start in range(0, len(chunks), batch_size):
            batch = chunks[batch_start : batch_start + batch_size]
            texts = [c.content for c in batch]

            async with profile_memory("embedding", source=source, n_chunks=len(batch)):
                embeddings = await provider.embed_documents(texts)

            batch_rows: list[DocumentChunk] = []
            for chunk, embedding in zip(batch, embeddings):
                row = DocumentChunk(
                    user_id=user_id,
                    source_name=chunk.source_name,
                    content=chunk.content,
                    chunk_content_hash=chunk.chunk_content_hash,
                    chapter=chunk.chapter,
                    section=chunk.section,
                    subsection=chunk.subsection,
                    embedding=embedding,
                    embedding_model=provider.model_name,
                    embedding_provider=provider.provider_name,
                    token_count=chunk.token_count,
                )
                session.add(row)
                batch_rows.append(row)

            async with profile_memory("vectorstore_write", source=source, n_rows=len(batch_rows)):
                await session.flush()

            all_rows.extend(batch_rows)

        logger.info(
            "Stored %d chunks for user_id=%d, source='%s'",
            len(all_rows),
            user_id,
            source,
        )
        return all_rows

    async def similarity_search(
        self,
        session: AsyncSession,
        user_id: int,
        query_embedding: list[float],
        limit: int = 5,
        source_names: list[str] | None = None,
        similarity_threshold: float = 0.7,
        chapters: list[str] | None = None,
        sections: list[str] | None = None,
        subsections: list[str] | None = None,
    ) -> list[SimilarityResult]:
        """Find the most similar chunks using cosine similarity.

        Uses pgvector's ``cosine_distance`` via SQLAlchemy ORM.
        Cosine similarity = 1 - cosine distance.

        ``source_names`` restricts the search to a specific set of sources.
        Pass ``None`` (default) to search all sources for the user.
        """
        distance = DocumentChunk.embedding.cosine_distance(query_embedding)
        similarity = (literal(1) - distance).label("similarity")

        stmt = (
            select(DocumentChunk, similarity)
            .where(col(DocumentChunk.user_id) == user_id)
            .where(similarity >= similarity_threshold)
        )

        if source_names:
            stmt = stmt.where(col(DocumentChunk.source_name).in_(source_names))

        if chapters is not None:
            stmt = stmt.where(col(DocumentChunk.chapter).in_(chapters))
        if sections is not None:
            stmt = stmt.where(col(DocumentChunk.section).in_(sections))
        if subsections is not None:
            stmt = stmt.where(col(DocumentChunk.subsection).in_(subsections))

        stmt = stmt.order_by(distance).limit(limit)

        result = await session.execute(stmt)
        rows = result.all()

        return [SimilarityResult(chunk=row[0], similarity=row[1]) for row in rows]

    async def get_distinct_sections(
        self,
        session: AsyncSession,
        user_id: int,
        source_name: str,
    ) -> list[dict[str, str | None]]:
        """Return distinct (chapter, section, subsection) tuples for a source."""
        stmt = (
            select(
                DocumentChunk.chapter,
                DocumentChunk.section,
                DocumentChunk.subsection,
            )
            .where(col(DocumentChunk.user_id) == user_id)
            .where(col(DocumentChunk.source_name) == source_name)
            .distinct()
        )
        result = await session.execute(stmt)
        return [{"chapter": row[0], "section": row[1], "subsection": row[2]} for row in result.all()]

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
        result = await session.execute(stmt)
        return [row[0] for row in result.all()]
