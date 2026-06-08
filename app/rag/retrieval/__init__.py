"""RAG retrieval module — agentic context retrieval for one or more documents."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.lib.db import session_scope
from app.rag.retrieval.agent import get_context_via_agent
from app.rag.types import RAGContext

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel


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
