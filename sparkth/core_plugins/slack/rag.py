"""RAG dispatch for the Slack TA Bot plugin — agentic retrieval."""

import httpx
from langchain_core.exceptions import LangChainException
from langchain_core.language_models import BaseChatModel
from pydantic import ValidationError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core_plugins.slack.config import SlackConfig, get_slack_settings
from sparkth.core_plugins.slack.constants import (
    DRIVE_FILE_NOT_FOUND_MESSAGE,
    NO_FILES_RESOLVED_MESSAGE,
    RAG_NOT_READY_MESSAGE,
    RETRIEVAL_ERROR_MESSAGE,
)
from sparkth.core_plugins.slack.enums import ResponseType
from sparkth.core_plugins.slack.synthesis import synthesize_answer
from sparkth.lib.documents import Document, DocumentStatus
from sparkth.lib.llm import BaseChatProvider
from sparkth.lib.log import get_logger
from sparkth.lib.rag import (
    DocumentNotFoundError,
    RAGNotReadyError,
    RAGRetrievalError,
    agentic_retrieve_context,
    format_document_chunks_as_llm_context,
)

logger = get_logger(__name__)


async def _resolve_document_ids_for_sources(
    session: AsyncSession,
    user_id: int,
    allowed_sources: list[str],
) -> list[int]:
    """Resolve a list of source names to RAG-ready Document IDs for *user_id*.

    Returns Document IDs filtered to DocumentStatus.READY and is_deleted=False. When
    *allowed_sources* is empty, returns all ready owner document IDs ordered by
    Document.id ASC, capped at SlackSettings.max_agent_files.
    """
    max_agent_files = get_slack_settings().max_agent_files
    stmt = (
        select(Document)
        .where(
            col(Document.user_id) == user_id,
            col(Document.status) == DocumentStatus.READY,
            col(Document.is_deleted) == False,  # noqa: E712
        )
        .order_by(col(Document.id).asc())
    )

    if allowed_sources:
        stmt = stmt.where(col(Document.name).in_(allowed_sources))

    result = await session.exec(stmt)
    documents: list[Document] = list(result.all())
    document_ids = [document.id for document in documents if document.id is not None]

    if len(document_ids) > max_agent_files:
        logger.warning(
            "Slack agentic RAG: %d documents resolved for user=%d, capping at max_agent_files=%d",
            len(document_ids),
            user_id,
            max_agent_files,
        )
        document_ids = document_ids[:max_agent_files]

    return document_ids


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
      1. Resolve allowed_sources to RAG-ready Document IDs (or top-N owner documents
         when allowed_sources is empty).
      2. Retrieve relevant chunks via agentic_retrieve_context, which fans out
         internally across all already-validated document_ids.
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
    document_ids = await _resolve_document_ids_for_sources(session, user_id, config.allowed_sources)

    logger.info(
        "Slack agentic RAG: user=%d documents=%d sources=%s",
        user_id,
        len(document_ids),
        config.allowed_sources or "all",
    )

    if not document_ids:
        logger.warning(
            "Slack agentic RAG: no documents resolved for user=%d sources=%s",
            user_id,
            config.allowed_sources or "all",
        )
        return NO_FILES_RESOLVED_MESSAGE, ResponseType.NO_FILES_RESOLVED

    try:
        chunks = await agentic_retrieve_context(question, document_ids, agent_llm)
    except DocumentNotFoundError as exc:
        logger.error("Slack agentic RAG: document not found user=%d documents=%s: %s", user_id, document_ids, exc)
        return DRIVE_FILE_NOT_FOUND_MESSAGE, ResponseType.DRIVE_FILE_NOT_FOUND
    except RAGNotReadyError as exc:
        logger.warning("Slack agentic RAG: document not ready user=%d documents=%s: %s", user_id, document_ids, exc)
        return RAG_NOT_READY_MESSAGE, ResponseType.RAG_NOT_READY
    except RAGRetrievalError as exc:
        logger.error("Slack agentic RAG: retrieval error user=%d documents=%s: %s", user_id, document_ids, exc)
        return RETRIEVAL_ERROR_MESSAGE, ResponseType.RETRIEVAL_ERROR

    logger.info("Slack agentic RAG: %d chunks for user=%d", len(chunks), user_id)

    if not chunks:
        return config.fallback_message, ResponseType.FALLBACK

    formatted_context = format_document_chunks_as_llm_context(chunks)

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
