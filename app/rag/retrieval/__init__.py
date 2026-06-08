"""RAG retrieval module — agentic context retrieval for one or more files."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from app.lib.db import session_scope
from app.rag.retrieval.agent import get_context_via_agent
from app.rag.retrieval.utils import validate_files_ready
from app.rag.types import RAGContext, RetrievedChunk

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel


async def get_context_via_agent_with_isolated_session(
    query: str,
    file_id: int,
    user_id: int,
    llm: BaseChatModel,
) -> RAGContext:
    """Retrieve context for a single file using agentic section retrieval.

    Opens its own DB session so concurrent callers (asyncio.gather fan-out)
    do not share a session — AsyncSession is not concurrency-safe.

    Args:
        query: The user's natural-language query.
        file_id: File to retrieve context from.
        user_id: Owner of the file (row-level scope).
        llm: LangChain chat model used by the retrieval agent.

    Raises:
        DriveFileNotFoundError / RAGNotReadyError: file access/readiness failure.
        RAGRetrievalError: retrieval failed.
    """
    async with session_scope() as file_session:
        return await get_context_via_agent(file_session, user_id, file_id, query, llm)


async def agentic_retrieve_context(
    query: str,
    file_ids: list[int],
    user_id: int,
    llm: BaseChatModel,
) -> list[RetrievedChunk]:
    """Retrieve relevant document chunks for a query across the given files.

    Validates that every file is owned by the user and READY (raising otherwise),
    then uses agentic section retrieval per file and returns a flat list of
    RetrievedChunk. Opens its own database sessions.

    Args:
        query: The user's natural-language query.
        file_ids: Files to search. All must exist and be READY.
        user_id: Owner of the files (row-level scope).
        llm: LangChain chat model used by the retrieval agent.

    Returns:
        Flat list of RetrievedChunk across all files (empty if no matches).

    Raises:
        DriveFileNotFoundError: a file is missing or not owned by the user.
        RAGNotReadyError: a file exists but is not READY.
        RAGRetrievalError: retrieval failed.
    """
    if not file_ids:
        return []

    async with session_scope() as session:
        await validate_files_ready(session, user_id, file_ids)

    tasks = [get_context_via_agent_with_isolated_session(query, fid, user_id, llm) for fid in file_ids]
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
