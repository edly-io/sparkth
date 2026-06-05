"""RAG context retrieval"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.lib.db import session_scope
from app.lib.log import get_logger
from app.rag.agent import RAGSearchAgent

if TYPE_CHECKING:
    # Imported under TYPE_CHECKING only to avoid a runtime cycle: app.models.drive
    # imports RagStatus from app.lib.rag, which imports this module.
    from langchain_core.language_models import BaseChatModel

    from app.models.drive import DriveFile

from app.rag.config import get_rag_settings
from app.rag.enums import RagStatus
from app.rag.exceptions import DriveFileNotFoundError, RAGNotReadyError, RAGRetrievalError
from app.rag.store import ChunkStoreService, SimilarityResult
from app.rag.types import RAGContext, RetrievedChunk
from app.rag.utils import resolve_source_name

__all__ = ["RAGContext", "format_chunks_as_context", "get_context_via_agent", "retrieve_chunks"]

logger = get_logger(__name__)


async def _lookup_drive_file(
    session: AsyncSession,
    user_id: int,
    file_db_id: int,
) -> DriveFile:
    from app.models.drive import DriveFile  # lazy — see TYPE_CHECKING note on the cycle

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


async def get_context_via_agent(
    session: AsyncSession,
    user_id: int,
    file_db_id: int,
    query: str,
    llm: Any,
    limit: int = get_rag_settings().RAG_DEFAULT_CHUNKS,
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
    store = ChunkStoreService()
    drive_file = await _lookup_drive_file(session, user_id, file_db_id)
    source_name = resolve_source_name(drive_file)

    if not query.strip():
        query = source_name

    logger.info(
        "RAG retrieval via agent: user=%d file_db_id=%d source_name=%s query_len=%d",
        user_id,
        file_db_id,
        source_name,
        len(query),
    )

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

    try:
        results = await store.fetch_chunks_by_sections(
            session=session,
            user_id=user_id,
            source_name=source_name,
            section_keys=[s.model_dump() for s in decision.selected_sections],
            limit=limit,
        )
    except Exception as exc:
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
        formatted_text=format_chunks_as_context(source_name, results),
    )


async def _validate_files_ready(session: AsyncSession, user_id: int, file_ids: list[int]) -> None:
    """Verify every file is owned by user_id and in READY state.

    Raises:
        DriveFileNotFoundError: a file id is missing or not owned by the user.
        RAGNotReadyError: a file exists but its rag_status is not READY.
    """
    from app.models.drive import DriveFile  # lazy — see TYPE_CHECKING note on the cycle

    result = await session.exec(
        select(DriveFile).where(
            col(DriveFile.id).in_(file_ids),
            col(DriveFile.user_id) == user_id,
            col(DriveFile.is_deleted) == False,  # noqa: E712
        )
    )
    found = {f.id: f for f in result.all()}
    for file_id in file_ids:
        drive_file = found.get(file_id)
        if drive_file is None:
            logger.warning("DriveFile not found: id=%d user_id=%d", file_id, user_id)
            raise DriveFileNotFoundError(f"File with id={file_id} not found or not accessible.")
        if drive_file.rag_status != RagStatus.READY:
            status_str = str(drive_file.rag_status or "None")
            logger.warning("RAG not ready: file_db_id=%d status=%s", file_id, status_str)
            raise RAGNotReadyError(file_id, status_str)


async def _search_one_file(
    user_id: int,
    file_id: int,
    query: str,
    llm: BaseChatModel,
) -> RAGContext:
    """Run the per-file agent search in its own session (for concurrent fan-out)."""
    async with session_scope() as file_session:
        return await get_context_via_agent(
            session=file_session,
            user_id=user_id,
            file_db_id=file_id,
            query=query,
            llm=llm,
        )


async def retrieve_chunks(
    user_id: int,
    file_ids: list[int],
    query: str,
    llm: BaseChatModel,
) -> list[RetrievedChunk]:
    """Validate all files are READY, then fan out agent retrieval per file.

    Returns a flat list of RetrievedChunk across all files (file_ids order).

    Raises:
        DriveFileNotFoundError / RAGNotReadyError: validation failed (nothing searched).
        RAGRetrievalError: a per-file agent search or section fetch failed.
    """
    if not file_ids:
        return []

    async with session_scope() as session:
        await _validate_files_ready(session, user_id, file_ids)

    tasks = [_search_one_file(user_id, fid, query, llm) for fid in file_ids]
    contexts = await asyncio.gather(*tasks)

    return [
        RetrievedChunk(
            source_name=sr.chunk.source_name,
            chapter=sr.chunk.chapter,
            section=sr.chunk.section,
            subsection=sr.chunk.subsection,
            content=sr.chunk.content,
        )
        for ctx in contexts
        for sr in ctx.chunks
    ]
