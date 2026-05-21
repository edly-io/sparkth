"""RAG dispatch for the Slack TA Bot plugin — agentic retrieval."""

import asyncio
from typing import Any

import httpx
from langchain_core.exceptions import LangChainException
from pydantic import ValidationError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logger import get_logger
from app.core_plugins.slack.config import SlackConfig
from app.core_plugins.slack.models import ResponseType
from app.core_plugins.slack.synthesis import synthesize_answer
from app.llm.providers import BaseChatProvider
from app.models.drive import DriveFile
from app.rag.context_service import RAGContextService, format_chunks_as_context
from app.rag.exceptions import (
    DriveFileNotFoundError,
    RAGNotReadyError,
    RAGRetrievalError,
)
from app.rag.store import SimilarityResult
from app.rag.types import RAGContext, RagStatus
from app.rag.utils import resolve_source_name

logger = get_logger(__name__)

# Module-level singleton — vector store and embedding provider loaded once per process.
# Reused only for its agentic entry point (get_context_via_agent); no semantic search runs.
_rag_service: RAGContextService = RAGContextService()

# Cap on files when allowed_sources is empty (broad fan-out across owner files).
_MAX_AGENT_FILES = 5

_NO_FILES_RESOLVED_MESSAGE = (
    "I don't have any documents available to answer that. "
    "Please ask your instructor to add documents to my reference list."
)
_RAG_NOT_READY_MESSAGE = "I'm still indexing the course documents. Please try again in a few minutes."
_DRIVE_FILE_NOT_FOUND_MESSAGE = (
    "I couldn't access one of my reference documents. Please ask your instructor to check the bot's configured sources."
)
_RETRIEVAL_ERROR_MESSAGE = "Something went wrong while looking that up. Please try again in a moment."


async def _resolve_files_for_sources(
    session: AsyncSession,
    user_id: int,
    allowed_sources: list[str],
) -> list[int]:
    """Resolve a list of source names to RAG-ready DriveFile IDs for *user_id*.

    Returns matching DriveFile IDs filtered to rag_status=READY and is_deleted=False.
    When *allowed_sources* is empty, returns all ready owner files ordered by
    DriveFile.id ASC, capped at _MAX_AGENT_FILES.
    """
    stmt = (
        select(DriveFile)
        .where(
            col(DriveFile.user_id) == user_id,
            col(DriveFile.rag_status) == RagStatus.READY,
            col(DriveFile.is_deleted) == False,  # noqa: E712
        )
        .order_by(col(DriveFile.id).asc())
    )
    result = await session.execute(stmt)
    files: list[DriveFile] = list(result.scalars().all())

    if allowed_sources:
        allowed_set = set(allowed_sources)
        return [f.id for f in files if f.id is not None and resolve_source_name(f) in allowed_set]

    return [f.id for f in files[:_MAX_AGENT_FILES] if f.id is not None]


async def _run_agent_fan_out(
    session: AsyncSession,
    user_id: int,
    file_ids: list[int],
    question: str,
    agent_llm: Any,
) -> list[RAGContext]:
    """Run agentic RAG per file concurrently. Any per-file failure propagates."""
    if not file_ids:
        return []

    coros = [
        _rag_service.get_context_via_agent(
            session=session,
            user_id=user_id,
            file_db_id=file_id,
            query=question,
            llm=agent_llm,
        )
        for file_id in file_ids
    ]
    return await asyncio.gather(*coros)


async def answer_question(
    session: AsyncSession,
    user_id: int,
    question: str,
    config: SlackConfig,
    agent_llm: Any,
    llm_provider: BaseChatProvider | None = None,
) -> tuple[str, ResponseType]:
    """Run agentic RAG for the bot's allowed_sources and return (answer, response_type).

    Steps:
      1. Resolve allowed_sources to RAG-ready DriveFile IDs (or top-N owner files
         when allowed_sources is empty).
      2. Fan out per file: each file gets one get_context_via_agent call, run
         concurrently via asyncio.gather.
      3. Aggregate. If no chunks are returned across any file, reply with the
         configured fallback_message.
      4. Optionally synthesize via LLM; otherwise return formatted raw chunks.

    Each operational failure mode maps to its own distinct user-facing message and
    ResponseType. config.fallback_message is reserved ONLY for the case where the
    agent ran successfully but found no relevant chunks.

    Args:
        session: Async SQLModel session.
        user_id: Bot owner (RLS scope).
        question: Cleaned student question (mention stripped).
        config: Per-bot SlackConfig (allowed_sources, fallback_message, ...).
        agent_llm: LangChain LLM used by the per-file agentic search. Required.
            Built from SYSTEM_LLM_* env vars by the caller; deployer pays.
        llm_provider: Optional BaseChatProvider for synthesis. When None, the bot
            returns formatted raw chunks. Built from the bot's llm_config_id by
            the caller; instructor pays.
    """
    file_ids = await _resolve_files_for_sources(
        session=session, user_id=user_id, allowed_sources=config.allowed_sources
    )

    logger.info(
        "Slack agentic RAG: user=%d files=%d sources=%s",
        user_id,
        len(file_ids),
        config.allowed_sources or "all",
    )

    if not file_ids:
        logger.warning(
            "Slack agentic RAG: no files resolved for user=%d sources=%s",
            user_id,
            config.allowed_sources or "all",
        )
        return _NO_FILES_RESOLVED_MESSAGE, ResponseType.no_files_resolved

    try:
        contexts = await _run_agent_fan_out(
            session=session,
            user_id=user_id,
            file_ids=file_ids,
            question=question,
            agent_llm=agent_llm,
        )
    except DriveFileNotFoundError as exc:
        logger.error("Slack agentic RAG: file not found user=%d files=%s: %s", user_id, file_ids, exc)
        return _DRIVE_FILE_NOT_FOUND_MESSAGE, ResponseType.drive_file_not_found
    except RAGNotReadyError as exc:
        logger.warning("Slack agentic RAG: file not ready user=%d files=%s: %s", user_id, file_ids, exc)
        return _RAG_NOT_READY_MESSAGE, ResponseType.rag_not_ready
    except RAGRetrievalError as exc:
        logger.error("Slack agentic RAG: retrieval error user=%d files=%s: %s", user_id, file_ids, exc)
        return _RETRIEVAL_ERROR_MESSAGE, ResponseType.retrieval_error

    non_empty = [c for c in contexts if c.chunks]
    total_chunks = sum(len(c.chunks) for c in non_empty)
    logger.info(
        "Slack agentic RAG: %d/%d files returned chunks, total_chunks=%d",
        len(non_empty),
        len(contexts),
        total_chunks,
    )

    if not non_empty:
        return config.fallback_message, ResponseType.fallback

    # Group all chunks by source_name and format using the existing helper.
    # Preserves the per-source "[DOCUMENT CONTEXT: <source>]" block layout.
    results_by_source: dict[str, list[SimilarityResult]] = {}
    sources_seen: list[str] = []
    for ctx in non_empty:
        for r in ctx.chunks:
            sname = r.chunk.source_name
            if sname not in results_by_source:
                sources_seen.append(sname)
                results_by_source[sname] = []
            results_by_source[sname].append(r)

    formatted_context = "\n\n".join(format_chunks_as_context(sname, results_by_source[sname]) for sname in sources_seen)

    if llm_provider:
        try:
            answer = await synthesize_answer(
                question=question,
                context=formatted_context,
                provider=llm_provider,
            )
            return answer, ResponseType.rag_match
        except (LangChainException, ValidationError, ValueError, RuntimeError, httpx.RemoteProtocolError) as exc:
            logger.warning(
                "LLM synthesis failed for user_id=%d, falling back to raw chunks: %s: %s",
                user_id,
                type(exc).__name__,
                exc,
            )
            return (
                f"Could not generate an AI summary, but here is what RAG found:\n\n{formatted_context}",
                ResponseType.rag_match,
            )

    return (
        f"AI summary is not available, but here is what RAG found:\n\n{formatted_context}",
        ResponseType.rag_match,
    )
