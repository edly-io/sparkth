"""RAG context retrieval for chat course generation."""

from dataclasses import dataclass
from typing import cast

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logger import get_logger
from app.models.drive import DriveFile
from app.rag.embeddings import BaseEmbeddingProvider, HuggingFaceEmbeddingProvider
from app.rag.exceptions import DriveFileNotFoundError, RAGNotReadyError, RAGRetrievalError
from app.rag.store import SimilarityResult, VectorStoreService
from app.rag.types import RagStatus

logger = get_logger(__name__)

_GOOGLE_NATIVE_MIMES = frozenset(
    {
        "application/vnd.google-apps.document",
        "application/vnd.google-apps.spreadsheet",
        "application/vnd.google-apps.presentation",
        "application/vnd.google-apps.drawing",
    }
)

DEFAULT_RAG_CHUNKS = 12
DEFAULT_SIMILARITY_THRESHOLD = 0.45
DEFAULT_TOP_SECTIONS = 8
LOW_SIMILARITY_THRESHOLD = 0.15


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors (pure Python, no numpy)."""
    dot: float = sum(x * y for x, y in zip(a, b))
    norm_a: float = sum(x * x for x in a) ** 0.5
    norm_b: float = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


@dataclass
class RAGContext:
    """Retrieved context ready for injection into an LLM prompt."""

    file_db_id: int
    source_name: str
    chunks: list[SimilarityResult]
    formatted_text: str
    ranked_sections: list[dict[str, str | None]] | None = None


class RAGContextService:
    """Retrieves relevant document chunks from the vector store for a given query."""

    def __init__(
        self,
        vector_store: VectorStoreService | None = None,
        embedding_provider: BaseEmbeddingProvider | None = None,
    ) -> None:
        self._store = vector_store or VectorStoreService()
        self._embedding_provider = embedding_provider or HuggingFaceEmbeddingProvider()

    async def get_context_for_drive_file(
        self,
        session: AsyncSession,
        user_id: int,
        file_db_id: int,
        query: str,
        limit: int = DEFAULT_RAG_CHUNKS,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    ) -> RAGContext:
        """Retrieve RAG context for a query against a specific Drive file.

        Raises:
            DriveFileNotFoundError: File not found or not owned by user.
            RAGNotReadyError: File exists but rag_status is not READY.
            RAGRetrievalError: Embedding or similarity search failed.
        """
        drive_file = await self._lookup_drive_file(session, user_id, file_db_id)
        source_name = _resolve_source_name(drive_file)

        # When the user sends only a file with no accompanying text, fall back to
        # the file name so the embedding is semantically meaningful.
        if not query.strip():
            query = source_name

        logger.info(
            "RAG retrieval: user=%d file_db_id=%d source_name=%s query_len=%d",
            user_id,
            file_db_id,
            source_name,
            len(query),
        )

        try:
            query_embedding = await self._embedding_provider.embed_query(query)
        except (RuntimeError, ValueError, OSError) as exc:
            logger.error("Failed to embed query for file_db_id=%d: %s", file_db_id, exc)
            raise RAGRetrievalError(f"Failed to embed query: {exc}") from exc

        ranked_sections = await self._rank_sections(
            session=session,
            user_id=user_id,
            source_name=source_name,
            query_embedding=query_embedding,
        )

        section_filter = list({s["section"] for s in ranked_sections if s["section"]}) or None

        logger.info(
            "RAG section ranking for file_db_id=%d: %d sections selected",
            file_db_id,
            len(ranked_sections),
        )

        try:
            results = await self._store.similarity_search(
                session=session,
                user_id=user_id,
                query_embedding=query_embedding,
                limit=limit,
                source_names=[source_name],
                similarity_threshold=similarity_threshold,
                sections=section_filter,
            )
        except SQLAlchemyError as exc:
            logger.error("Similarity search failed for file_db_id=%d: %s", file_db_id, exc)
            raise RAGRetrievalError(f"Similarity search failed: {exc}") from exc

        logger.info("RAG: found %d chunks for file_db_id=%d", len(results), file_db_id)
        logger.info(
            "RAG chunk IDs in context for file_db_id=%d: %s",
            file_db_id,
            [r.chunk.id for r in results],
        )

        return RAGContext(
            file_db_id=file_db_id,
            source_name=source_name,
            chunks=results,
            formatted_text=_format_chunks_as_context(source_name, results),
            ranked_sections=ranked_sections,
        )

    async def rank_sections_for_query(
        self,
        session: AsyncSession,
        user_id: int,
        file_db_id: int,
        query: str,
    ) -> tuple[str, list[float], list[dict[str, str | None]]]:
        """Phase 1: embed query and rank sections by title similarity.

        Returns (source_name, query_embedding, ranked_sections).

        Raises:
            DriveFileNotFoundError: File not found or not owned by user.
            RAGNotReadyError: File exists but rag_status is not READY.
            RAGRetrievalError: Embedding failed.
        """
        drive_file = await self._lookup_drive_file(session, user_id, file_db_id)
        source_name = _resolve_source_name(drive_file)

        try:
            query_embedding = await self._embedding_provider.embed_query(query)
        except (RuntimeError, ValueError, OSError) as exc:
            logger.error("Failed to embed query for file_db_id=%d: %s", file_db_id, exc)
            raise RAGRetrievalError(f"Failed to embed query: {exc}") from exc

        ranked_sections = await self._rank_sections(
            session=session,
            user_id=user_id,
            source_name=source_name,
            query_embedding=query_embedding,
        )
        return source_name, query_embedding, ranked_sections

    async def search_with_embedding(
        self,
        session: AsyncSession,
        user_id: int,
        source_name: str,
        query_embedding: list[float],
        limit: int = DEFAULT_RAG_CHUNKS,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        sections: list[str] | None = None,
    ) -> list[SimilarityResult]:
        """Phase 2: similarity search with pre-computed query embedding.

        Raises:
            RAGRetrievalError: Database query failed.
        """
        try:
            results = await self._store.similarity_search(
                session=session,
                user_id=user_id,
                query_embedding=query_embedding,
                limit=limit,
                source_names=[source_name],
                similarity_threshold=similarity_threshold,
                sections=sections,
            )
        except SQLAlchemyError as exc:
            logger.error("Similarity search failed for source_name=%s: %s", source_name, exc)
            raise RAGRetrievalError(f"Similarity search failed: {exc}") from exc

        logger.info("RAG: found %d chunks for source_name=%s", len(results), source_name)
        logger.info("RAG chunk IDs in context: %s", [r.chunk.id for r in results])
        return results

    async def _rank_sections(
        self,
        session: AsyncSession,
        user_id: int,
        source_name: str,
        query_embedding: list[float],
        top_n: int = DEFAULT_TOP_SECTIONS,
    ) -> list[dict[str, str | None]]:
        """Rank document sections by title similarity to the query embedding."""
        all_sections = await self._store.get_distinct_sections(session, user_id, source_name)
        if not all_sections:
            return []

        section_titles = []
        for sec in all_sections:
            parts: list[str] = [cast(str, sec[k]) for k in ("chapter", "section", "subsection") if sec[k]]
            section_titles.append(" / ".join(parts) if parts else "General")

        title_embeddings = await self._embedding_provider.embed_documents(section_titles)

        scored: list[tuple[float, dict[str, str | None]]] = []
        for i, title_emb in enumerate(title_embeddings):
            sim = _cosine_similarity(query_embedding, title_emb)
            scored.append((sim, all_sections[i]))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [s[1] for s in scored[:top_n]]

    async def _lookup_drive_file(
        self,
        session: AsyncSession,
        user_id: int,
        file_db_id: int,
    ) -> DriveFile:
        result = await session.execute(
            select(DriveFile).where(
                col(DriveFile.id) == file_db_id,
                col(DriveFile.user_id) == user_id,
                col(DriveFile.is_deleted) == False,  # noqa: E712
            )
        )
        drive_file_raw = result.scalars().first()

        if drive_file_raw is None:
            logger.warning("DriveFile not found: id=%d user_id=%d", file_db_id, user_id)
            raise DriveFileNotFoundError(f"File with id={file_db_id} not found or not accessible.")

        drive_file = cast(DriveFile, drive_file_raw)

        if drive_file.rag_status != RagStatus.READY:
            status_str = str(drive_file.rag_status or "None")
            logger.warning("RAG not ready: file_db_id=%d status=%s", file_db_id, status_str)
            raise RAGNotReadyError(file_db_id, status_str)

        return drive_file


def _resolve_source_name(drive_file: DriveFile) -> str:
    """Return the source_name as stored in DocumentChunk."""
    filename = drive_file.name
    mime_type = drive_file.mime_type or ""
    if mime_type in _GOOGLE_NATIVE_MIMES and not filename.lower().endswith(".pdf"):
        filename = f"{filename}.pdf"
    return filename


def _format_chunks_as_context(source_name: str, results: list[SimilarityResult]) -> str:
    """Format retrieved chunks as a structured text block for the LLM."""
    if not results:
        return f"[DOCUMENT CONTEXT: {source_name}]\nNo relevant excerpts found."

    lines: list[str] = [
        f"[DOCUMENT CONTEXT: {source_name}]",
        "The following excerpts were retrieved from the document to inform your response:",
        "",
    ]
    for i, sr in enumerate(results, 1):
        chunk = sr.chunk
        header_parts = [p for p in [chunk.chapter, chunk.section, chunk.subsection] if p]
        section_label = " / ".join(header_parts) if header_parts else "General"
        lines.append(f"--- Excerpt {i} (Section: {section_label}) ---")
        lines.append(chunk.content.strip())
        lines.append("")

    return "\n".join(lines)
