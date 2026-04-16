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
DEFAULT_SIMILARITY_THRESHOLD = 0.7


@dataclass
class RAGContext:
    """Retrieved context ready for injection into an LLM prompt."""

    file_db_id: int
    source_name: str
    chunks: list[SimilarityResult]
    formatted_text: str


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

        try:
            results = await self._store.similarity_search(
                session=session,
                user_id=user_id,
                query_embedding=query_embedding,
                limit=limit,
                source_name=source_name,
                similarity_threshold=similarity_threshold,
            )
        except SQLAlchemyError as exc:
            logger.error("Similarity search failed for file_db_id=%d: %s", file_db_id, exc)
            raise RAGRetrievalError(f"Similarity search failed: {exc}") from exc

        logger.info("RAG: found %d chunks for file_db_id=%d", len(results), file_db_id)

        return RAGContext(
            file_db_id=file_db_id,
            source_name=source_name,
            chunks=results,
            formatted_text=_format_chunks_as_context(source_name, results),
        )

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
