"""RAG retrieval module — agentic context retrieval for one or more documents."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from app.lib.db import session_scope
from app.rag.retrieval.agent import get_context_via_agent
from app.rag.retrieval.utils import validate_files_ready
from app.rag.types import RAGContext, RetrievedChunk

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel


async def agentic_retrieve_context(
    user_id: int,
    document_ids: list[int],
    query: str,
    llm: BaseChatModel,
) -> list[RetrievedChunk]:
    """Retrieve relevant document chunks for a query across the given documents.

    Validates that every document is owned by the user and READY (raising
    otherwise), then uses agentic section retrieval per document and returns a
    flat list of RetrievedChunk. Opens its own database sessions.

    Args:
        user_id: Owner of the documents (row-level scope).
        document_ids: Documents to search. All must exist and be READY.
        query: The user's natural-language query.
        llm: LangChain chat model used by the retrieval agent.

    Returns:
        Flat list of RetrievedChunk across all documents (empty if no matches).

    Raises:
        DocumentNotFoundError: a document is missing or not owned by the user.
        RAGNotReadyError: a document exists but is not READY.
        RAGRetrievalError: retrieval failed.
    """
    if not document_ids:
        return []

    async with session_scope() as session:
        await validate_files_ready(session, user_id, document_ids)

    tasks = [get_context_via_agent_with_isolated_session(user_id, did, query, llm) for did in document_ids]
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


async def get_context_via_agent_with_isolated_session(
    user_id: int,
    document_id: int,
    query: str,
    llm: BaseChatModel,
) -> RAGContext:
    """Retrieve context for a single document using agentic section retrieval.

    Opens its own DB session so concurrent callers (asyncio.gather fan-out)
    do not share a session — AsyncSession is not concurrency-safe.

    Args:
        user_id: Owner of the document (row-level scope).
        document_id: Document.id to retrieve context from.
        query: The user's natural-language query.
        llm: LangChain chat model used by the retrieval agent.

    Raises:
        DocumentNotFoundError / RAGNotReadyError: document access/readiness failure.
        RAGRetrievalError: retrieval failed.
    """
    async with session_scope() as file_session:
        return await get_context_via_agent(file_session, user_id, document_id, query, llm)
