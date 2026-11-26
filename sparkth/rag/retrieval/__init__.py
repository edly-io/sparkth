"""RAG retrieval module — agentic context retrieval for one or more documents."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from sparkth.lib.auth import current_user_id
from sparkth.lib.db import session_scope
from sparkth.lib.documents import DocumentStatus, get_document
from sparkth.rag.config import get_rag_settings
from sparkth.rag.retrieval.agent import get_context_via_agent
from sparkth.rag.retrieval.utils import validate_documents_ready
from sparkth.rag.store import ChunkStoreService
from sparkth.rag.types import RAGContext, RetrievedChunk

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel


async def agentic_retrieve_context(
    query: str,
    document_ids: list[int],
    llm: BaseChatModel,
) -> list[RetrievedChunk]:
    """Retrieve relevant document chunks for a query across the given documents.

    Validates that every document exists and is READY before retrieval — callers
    do not need to perform this check themselves. Uses agentic section retrieval
    per document and returns a flat list of RetrievedChunk. Opens its own database
    sessions.

    Args:
        document_ids: Documents to search. All must exist and be READY.
        query: The user's natural-language query.
        llm: LangChain chat model used by the retrieval agent.

    Returns:
        Flat list of RetrievedChunk across all documents (empty if no matches).

    Raises:
        DocumentNotFoundError: a document is missing or soft-deleted.
        RAGNotReadyError: a document exists but is not READY.
        RAGRetrievalError: retrieval failed.
    """
    if not document_ids:
        return []

    async with session_scope() as session:
        await validate_documents_ready(session, document_ids)

    tasks = [get_context_via_agent_with_isolated_session(did, query, llm) for did in document_ids]
    contexts = await asyncio.gather(*tasks)

    return [
        RetrievedChunk(
            source_name=chunk.source_name,
            chapter=chunk.chapter,
            section=chunk.section,
            subsection=chunk.subsection,
            content=chunk.content,
        )
        for ctx in contexts
        for chunk in ctx.chunks
    ]


async def get_context_via_agent_with_isolated_session(
    document_id: int,
    query: str,
    llm: BaseChatModel,
) -> RAGContext:
    """Retrieve context for a single document using agentic section retrieval.

    Opens its own DB session so concurrent callers (asyncio.gather fan-out)
    do not share a session — AsyncSession is not concurrency-safe.

    Args:
        document_id: Document.id to retrieve context from.
        query: The user's natural-language query.
        llm: LangChain chat model used by the retrieval agent.

    Raises:
        DocumentNotFoundError / RAGNotReadyError: document lookup/readiness failure.
        RAGRetrievalError: retrieval failed.
    """
    async with session_scope() as document_session:
        return await get_context_via_agent(document_session, document_id, query, llm)


async def get_section_chunks(document_id: int, sections: list[dict[str, str | None]]) -> list[RetrievedChunk]:
    """Return the chunks of ``sections`` of ``document_id``, in document order.

    Each section is a dict of ``chapter``, ``section`` and ``subsection``, matched exactly. Reads
    only a ready document the requesting user owns; any other has no chunks.
    """
    async with session_scope() as session:
        document = await get_document(session, document_id, current_user_id())
        if document is None or document.status != DocumentStatus.READY:
            return []
        chunks = await ChunkStoreService().fetch_chunks_by_sections(
            session, document_id, sections, get_rag_settings().RAG_DEFAULT_CHUNKS
        )
    return [
        RetrievedChunk(
            source_name=chunk.source_name,
            chapter=chunk.chapter,
            section=chunk.section,
            subsection=chunk.subsection,
            content=chunk.content,
        )
        for chunk in chunks
    ]
