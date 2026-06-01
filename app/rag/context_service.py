"""RAG context retrieval for chat course generation."""

from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logger import get_logger
from app.models.drive import DriveFile
from app.rag import constants
from app.rag.agent import RAGSearchAgent
from app.rag.exceptions import DriveFileNotFoundError, RAGNotReadyError, RAGRetrievalError
from app.rag.store import SimilarityResult, VectorStoreService
from app.rag.types import RAGContext, RagStatus
from app.rag.utils import resolve_source_name

# Re-export for backwards-compatibility with modules that import from context_service
__all__ = ["RAGContext", "RAGContextService", "format_chunks_as_context"]

logger = get_logger(__name__)


class RAGContextService:
    """Retrieves relevant document chunks for a given query via agent-driven section selection."""

    def __init__(
        self,
        vector_store: VectorStoreService | None = None,
    ) -> None:
        self._store = vector_store or VectorStoreService()

    async def get_context_via_agent(
        self,
        session: AsyncSession,
        user_id: int,
        file_db_id: int,
        query: str,
        llm: Any,
        limit: int = constants.DEFAULT_RAG_CHUNKS,
    ) -> RAGContext:
        """Retrieve RAG context by agent-driven section selection.

        A LangGraph ReAct agent inspects the document structure via MCP tools,
        understands the user's intent, and hand-picks the relevant sections.
        All chunks in those sections are fetched directly — no similarity search.

        Raises:
            DriveFileNotFoundError: File not found or not owned by user.
            RAGNotReadyError: File exists but rag_status is not READY.
            RAGRetrievalError: Agent invocation or section fetch failed.
        """
        # Lookup file and verify access/readiness
        drive_file = await self._lookup_drive_file(session, user_id, file_db_id)
        source_name = resolve_source_name(drive_file)

        # Empty query fallback: use source name
        if not query.strip():
            query = source_name

        logger.info(
            "RAG retrieval via agent: user=%d file_db_id=%d source_name=%s query_len=%d",
            user_id,
            file_db_id,
            source_name,
            len(query),
        )

        # Call agent to hand-pick sections based on user intent
        decision = await RAGSearchAgent().search(
            llm=llm,
            user_id=user_id,
            file_id=file_db_id,
            user_query=query,
        )

        logger.info(
            "RAG agent selected %d section(s) for file_db_id=%d",
            len(decision.selected_sections),
            file_db_id,
        )

        # Fetch chunks directly for the agent-selected sections — no similarity search
        try:
            results = await self._store.fetch_chunks_by_sections(
                session=session,
                user_id=user_id,
                source_name=source_name,
                section_keys=[s.model_dump() for s in decision.selected_sections],
                limit=limit,
            )
        except SQLAlchemyError as exc:
            logger.error("Section fetch failed for file_db_id=%d: %s", file_db_id, exc)
            raise RAGRetrievalError(f"Section fetch failed: {exc}") from exc

        logger.info("RAG: found %d chunks for file_db_id=%d via agent", len(results), file_db_id)
        logger.info(
            "RAG chunk IDs in context for file_db_id=%d: %s",
            file_db_id,
            [r.chunk.id for r in results],
        )

        return RAGContext(
            file_db_id=file_db_id,
            source_name=source_name,
            chunks=results,
            formatted_text=self.format_chunks_as_context(source_name, results),
        )

    @staticmethod
    def format_chunks_as_context(source_name: str, results: list[SimilarityResult]) -> str:
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

    async def _lookup_drive_file(
        self,
        session: AsyncSession,
        user_id: int,
        file_db_id: int,
    ) -> DriveFile:
        result = await session.exec(
            select(DriveFile).where(
                col(DriveFile.id) == file_db_id,
                col(DriveFile.user_id) == user_id,
                col(DriveFile.is_deleted) == False,  # noqa: E712
            )
        )
        drive_file_raw: DriveFile | None = result.first()

        if drive_file_raw is None:
            logger.warning("DriveFile not found: id=%d user_id=%d", file_db_id, user_id)
            raise DriveFileNotFoundError(f"File with id={file_db_id} not found or not accessible.")

        drive_file = drive_file_raw

        if drive_file.rag_status != RagStatus.READY:
            status_str = str(drive_file.rag_status or "None")
            logger.warning("RAG not ready: file_db_id=%d status=%s", file_db_id, status_str)
            raise RAGNotReadyError(file_db_id, status_str)

        return drive_file


# Backward-compatibility alias
format_chunks_as_context = RAGContextService.format_chunks_as_context
