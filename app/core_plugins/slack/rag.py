"""RAG dispatch for the Slack TA Bot plugin — agentic retrieval."""

import asyncio
from collections import Counter

import httpx
from langchain_core.exceptions import LangChainException
from langchain_core.language_models import BaseChatModel
from pydantic import ValidationError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core_plugins.slack.config import SlackConfig, get_slack_settings
from app.core_plugins.slack.constants import (
    DRIVE_FILE_NOT_FOUND_MESSAGE,
    NO_FILES_RESOLVED_MESSAGE,
    RAG_NOT_READY_MESSAGE,
    RETRIEVAL_ERROR_MESSAGE,
)
from app.core_plugins.slack.enums import ResponseType
from app.core_plugins.slack.synthesis import synthesize_answer
from app.lib.db import session_scope
from app.lib.log import get_logger
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

# Most-informative-first priority when all files fail and we must pick one error to raise.
_ERROR_PRIORITY: tuple[type[BaseException], ...] = (
    DriveFileNotFoundError,
    RAGNotReadyError,
    RAGRetrievalError,
)


def _pick_representative_error(errors: list[BaseException]) -> BaseException:
    for exc_type in _ERROR_PRIORITY:
        for e in errors:
            if isinstance(e, exc_type):
                return e
    return errors[0]


async def _resolve_files_for_sources(
    session: AsyncSession,
    user_id: int,
    allowed_sources: list[str],
) -> list[int]:
    """Resolve a list of source names to RAG-ready DriveFile IDs for *user_id*.

    Returns matching DriveFile IDs filtered to rag_status=READY and is_deleted=False.
    When *allowed_sources* is empty, returns all ready owner files ordered by
    DriveFile.id ASC, capped at SlackSystemConfig.MAX_AGENT_FILES.
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

    if allowed_sources:
        # resolve_source_name appends .pdf for Google-native MIME types whose
        # DriveFile.name has no .pdf suffix. Build a candidate set covering both
        # the resolved name (regular files) and the stripped name (Google-native
        # docs) so the SQL scan stays bounded even for large file libraries.
        candidate_names: set[str] = set()
        for s in allowed_sources:
            candidate_names.add(s)
            if s.lower().endswith(".pdf"):
                candidate_names.add(s[:-4])
        stmt = stmt.where(col(DriveFile.name).in_(candidate_names))

    result = await session.exec(stmt)
    files: list[DriveFile] = list(result.all())
    max_files = get_slack_settings().max_agent_files

    if allowed_sources:
        allowed_set = set(allowed_sources)
        matched = [f.id for f in files if f.id is not None and resolve_source_name(f) in allowed_set]
        if len(matched) > max_files:
            logger.warning(
                "Slack agentic RAG: %d sources resolved for user=%d, capping at MAX_AGENT_FILES=%d",
                len(matched),
                user_id,
                max_files,
            )
            matched = matched[:max_files]
        return matched

    return [f.id for f in files[:max_files] if f.id is not None]


async def _run_agent_fan_out(
    user_id: int,
    file_ids: list[int],
    question: str,
    agent_llm: BaseChatModel,
) -> list[RAGContext]:
    """Run agentic RAG per file concurrently with partial-failure tolerance.

    Uses return_exceptions=True so a single failing file does not discard results
    from files that succeeded. Each coroutine gets its own AsyncSession — sharing
    a single session across concurrent coroutines is unsafe (SQLAlchemy AsyncSession
    is not reentrant).

    If at least one file returns a RAGContext, the failures are logged and dropped.
    Only when ALL files fail is the representative exception re-raised to the caller.
    """
    if not file_ids:
        return []

    rag_service = RAGContextService()

    async def _run_single(file_id: int) -> RAGContext:
        async with session_scope() as file_session:
            return await rag_service.get_context_via_agent(
                file_session,
                user_id,
                file_id,
                question,
                agent_llm,
            )

    raw: list[RAGContext | BaseException] = await asyncio.gather(
        *[_run_single(fid) for fid in file_ids], return_exceptions=True
    )
    contexts = [r for r in raw if isinstance(r, RAGContext)]
    errors = [r for r in raw if isinstance(r, BaseException)]
    if errors:
        logger.warning(
            "Slack agentic RAG: %d/%d files failed for user=%d: %s",
            len(errors),
            len(file_ids),
            user_id,
            dict(Counter(type(e).__name__ for e in errors)),
        )
    if errors and not contexts:
        raise _pick_representative_error(errors)
    return contexts


async def answer_question(
    session: AsyncSession,
    user_id: int,
    question: str,
    config: SlackConfig,
    agent_llm: BaseChatModel,
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
            Built from the instructor's llm_config_id by the caller.
        llm_provider: Optional BaseChatProvider for synthesis. When None, the bot
            returns formatted raw chunks. Built from the instructor's llm_config_id
            by the caller.
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
        return NO_FILES_RESOLVED_MESSAGE, ResponseType.NO_FILES_RESOLVED

    try:
        contexts = await _run_agent_fan_out(
            user_id,
            file_ids,
            question,
            agent_llm,
        )
    except DriveFileNotFoundError as exc:
        logger.error("Slack agentic RAG: file not found user=%d files=%s: %s", user_id, file_ids, exc)
        return DRIVE_FILE_NOT_FOUND_MESSAGE, ResponseType.DRIVE_FILE_NOT_FOUND
    except RAGNotReadyError as exc:
        logger.warning("Slack agentic RAG: file not ready user=%d files=%s: %s", user_id, file_ids, exc)
        return RAG_NOT_READY_MESSAGE, ResponseType.RAG_NOT_READY
    except RAGRetrievalError as exc:
        logger.error("Slack agentic RAG: retrieval error user=%d files=%s: %s", user_id, file_ids, exc)
        return RETRIEVAL_ERROR_MESSAGE, ResponseType.RETRIEVAL_ERROR

    non_empty = [c for c in contexts if c.chunks]
    total_chunks = sum(len(c.chunks) for c in non_empty)
    logger.info(
        "Slack agentic RAG: %d/%d files returned chunks, total_chunks=%d",
        len(non_empty),
        len(contexts),
        total_chunks,
    )

    if not non_empty:
        return config.fallback_message, ResponseType.FALLBACK

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
                question,
                formatted_context,
                llm_provider,
            )
            return answer, ResponseType.RAG_MATCH
        except (LangChainException, ValidationError, ValueError, RuntimeError, httpx.RemoteProtocolError) as exc:
            logger.warning(
                "LLM synthesis failed for user_id=%d, falling back to raw chunks: %s: %s",
                user_id,
                type(exc).__name__,
                exc,
            )
            return (
                f"Could not generate an AI summary, but here is what RAG found:\n\n{formatted_context}",
                ResponseType.RAG_MATCH,
            )

    return (
        f"AI summary is not available, but here is what RAG found:\n\n{formatted_context}",
        ResponseType.RAG_MATCH,
    )
