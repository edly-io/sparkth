"""Vector store service for storing and retrieving document chunks."""

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import delete, text
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

        Uses pgvector's ``<=>`` (cosine distance) operator.
        Cosine similarity = 1 - cosine distance.
        """
        params: dict[str, object] = {
            "query_embedding": str(query_embedding),
            "user_id": user_id,
            "threshold": similarity_threshold,
            "limit": limit,
        }

        source_filter = ""
        if source_name is not None:
            source_filter = "AND source_name = :source_name"
            params["source_name"] = source_name

        stmt = text(f"""
            SELECT id, user_id, source_name, content, chapter, section, subsection,
                   embedding_model, embedding_provider, token_count,
                   created_at, updated_at,
                   1 - (embedding <=> :query_embedding::vector) AS similarity
            FROM rag_document_chunks
            WHERE user_id = :user_id
              AND 1 - (embedding <=> :query_embedding::vector) >= :threshold
              {source_filter}
            ORDER BY embedding <=> :query_embedding::vector
            LIMIT :limit
        """)

        result = await session.execute(stmt, params)
        rows = result.mappings().all()

        results: list[SimilarityResult] = []
        for row in rows:
            chunk = DocumentChunk(
                id=row["id"],
                user_id=row["user_id"],
                source_name=row["source_name"],
                content=row["content"],
                chapter=row["chapter"],
                section=row["section"],
                subsection=row["subsection"],
                embedding_model=row["embedding_model"],
                embedding_provider=row["embedding_provider"],
                token_count=row["token_count"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            results.append(SimilarityResult(chunk=chunk, similarity=row["similarity"]))

        return results

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
