"""RAG dispatch for the Slack TA Bot plugin — agentic retrieval."""

import httpx
from langchain_core.exceptions import LangChainException
from langchain_core.language_models import BaseChatModel
from pydantic import ValidationError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.documents.enums import DocumentStatus
from app.core.documents.models import Document
from app.core_plugins.slack.config import SlackConfig, get_slack_settings
from app.core_plugins.slack.constants import (
    DRIVE_FILE_NOT_FOUND_MESSAGE,
    NO_FILES_RESOLVED_MESSAGE,
    RAG_NOT_READY_MESSAGE,
    RETRIEVAL_ERROR_MESSAGE,
)
from app.core_plugins.slack.enums import ResponseType
from app.core_plugins.slack.synthesis import synthesize_answer
from app.lib.log import get_logger
from app.lib.rag import (
    DocumentNotFoundError,
    RAGNotReadyError,
    RAGRetrievalError,
    RetrievedChunk,
    agentic_retrieve_context,
)
from app.llm.providers import BaseChatProvider
from app.models.drive import DriveFile
from app.rag.utils import resolve_source_name

logger = get_logger(__name__)


# TODO: this function is almost similar to app.core_plugins.chat.routes.helpers.format_source_block
# we need to figure out how to remove this duplication.
def _format_context(chunks: list[RetrievedChunk]) -> str:
    """Render retrieved chunks as per-document context blocks for synthesis."""
    by_source: dict[str, list[RetrievedChunk]] = {}
    order: list[str] = []
    for c in chunks:
        if c.source_name not in by_source:
            order.append(c.source_name)
            by_source[c.source_name] = []
        by_source[c.source_name].append(c)

    blocks: list[str] = []
    for source in order:
        lines = [f"[DOCUMENT CONTEXT: {source}]", "The following excerpts were retrieved:", ""]
        for i, c in enumerate(by_source[source], 1):
            parts = [p for p in [c.chapter, c.section, c.subsection] if p]
            label = " / ".join(parts) if parts else "General"
            lines.append(f"--- Excerpt {i} (Section: {label}) ---")
            lines.append(c.content.strip())
            lines.append("")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


async def _resolve_files_for_sources(
    session: AsyncSession,
    user_id: int,
    allowed_sources: list[str],
) -> list[int]:
    """Resolve a list of source names to RAG-ready Document IDs for *user_id*.

    Returns Document IDs filtered to DocumentStatus.READY and is_deleted=False.
    When *allowed_sources* is empty, returns all ready owner document IDs ordered by
    DriveFile.id ASC, capped at SlackSettings.max_agent_files.
    """
    max_agent_files = get_slack_settings().max_agent_files
    stmt = (
        select(DriveFile)
        .join(Document, col(DriveFile.document_id) == col(Document.id))
        .where(
            col(DriveFile.user_id) == user_id,
            col(Document.status) == DocumentStatus.READY,
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

    if allowed_sources:
        allowed_set = set(allowed_sources)
        matched = [f.document_id for f in files if f.document_id is not None and resolve_source_name(f) in allowed_set]
        if len(matched) > max_agent_files:
            logger.warning(
                "Slack agentic RAG: %d sources resolved for user=%d, capping at max_agent_files=%d",
                len(matched),
                user_id,
                max_agent_files,
            )
            matched = matched[:max_agent_files]
        return matched

    return [f.document_id for f in files[:max_agent_files] if f.document_id is not None]


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
      2. Retrieve relevant chunks via agentic_retrieve_context (validates all files READY,
         fans out internally across all file_ids).
      3. If no chunks are returned, reply with the configured fallback_message.
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
    file_ids = await _resolve_files_for_sources(session, user_id, config.allowed_sources)

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
        chunks = await agentic_retrieve_context(question, file_ids, user_id, agent_llm)
    except DocumentNotFoundError as exc:
        logger.error("Slack agentic RAG: file not found user=%d files=%s: %s", user_id, file_ids, exc)
        return DRIVE_FILE_NOT_FOUND_MESSAGE, ResponseType.DRIVE_FILE_NOT_FOUND
    except RAGNotReadyError as exc:
        logger.warning("Slack agentic RAG: file not ready user=%d files=%s: %s", user_id, file_ids, exc)
        return RAG_NOT_READY_MESSAGE, ResponseType.RAG_NOT_READY
    except RAGRetrievalError as exc:
        logger.error("Slack agentic RAG: retrieval error user=%d files=%s: %s", user_id, file_ids, exc)
        return RETRIEVAL_ERROR_MESSAGE, ResponseType.RETRIEVAL_ERROR

    logger.info("Slack agentic RAG: %d chunks for user=%d", len(chunks), user_id)

    if not chunks:
        return config.fallback_message, ResponseType.FALLBACK

    formatted_context = _format_context(chunks)

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
