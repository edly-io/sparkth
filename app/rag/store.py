"""Vector store service for storing and retrieving document chunks."""

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import delete, literal
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logger import get_logger
from app.rag.embeddings import BaseEmbeddingProvider
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
    chapter: Optional[str] = None
    section: Optional[str] = None
    subsection: Optional[str] = None
    token_count: Optional[int] = None


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
        """Embed and persist a batch of chunks.

        Returns the created ``DocumentChunk`` rows (with IDs populated).
        """
        if not chunks:
            return []

        texts = [c.content for c in chunks]
        embeddings = await provider.embed_documents(texts)

        rows: list[DocumentChunk] = []
        for chunk, embedding in zip(chunks, embeddings):
            row = DocumentChunk(
                user_id=user_id,
                source_name=chunk.source_name,
                content=chunk.content,
                chapter=chunk.chapter,
                section=chunk.section,
                subsection=chunk.subsection,
                embedding=embedding,
                embedding_model=provider.model_name,
                embedding_provider=provider.provider_name,
                token_count=chunk.token_count,
            )
            session.add(row)
            rows.append(row)

        await session.flush()

        logger.info(
            "Stored %d chunks for user_id=%d, source='%s'",
            len(rows),
            user_id,
            chunks[0].source_name if chunks else "?",
        )
        return rows

    async def similarity_search(
        self,
        session: AsyncSession,
        user_id: int,
        query_embedding: list[float],
        limit: int = 5,
        source_name: Optional[str] = None,
        similarity_threshold: float = 0.7,
    ) -> list[SimilarityResult]:
        """Find the most similar chunks using cosine similarity.

        Uses pgvector's ``cosine_distance`` via SQLAlchemy ORM.
        Cosine similarity = 1 - cosine distance.
        """
        distance = DocumentChunk.embedding.cosine_distance(query_embedding)
        similarity = (literal(1) - distance).label("similarity")

        stmt = (
            select(DocumentChunk, similarity)
            .where(col(DocumentChunk.user_id) == user_id)
            .where(similarity >= similarity_threshold)
            .order_by(distance)
            .limit(limit)
        )

        if source_name is not None:
            stmt = stmt.where(col(DocumentChunk.source_name) == source_name)

        result = await session.execute(stmt)
        rows = result.all()

        return [SimilarityResult(chunk=row[0], similarity=row[1]) for row in rows]

    async def delete_by_source(
        self,
        session: AsyncSession,
        user_id: int,
        source_name: str,
    ) -> int:
        """Delete all chunks for a given source document. Returns count deleted."""
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
        stmt = select(DocumentChunk.source_name).where(col(DocumentChunk.user_id) == user_id).distinct()
        result = await session.execute(stmt)
        return [row[0] for row in result.all()]
