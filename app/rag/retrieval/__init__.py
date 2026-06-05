"""RAG retrieval module.

The retrieval registry maps retrieval method names to their implementation
functions. Each registered function has the signature:

    async def fn(
        session: AsyncSession,
        user_id: int,
        file_db_id: int,
        query: str,
        llm: Any,
    ) -> RAGContext

Available retrieval methods:
    "agentic" (default): LangGraph ReAct agent inspects the document structure
        via MCP tools, selects relevant sections, and fetches their chunks
        directly — no vector similarity search.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Coroutine

from app.lib.db import session_scope
from app.rag.retrieval.agent import get_context_via_agent
from app.rag.types import RAGContext

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

# Maps retrieval method name -> retrieval function.
# Add new retrieval methods here as additional entries.
RETRIEVAL_REGISTRY: dict[str, Callable[..., Coroutine[Any, Any, RAGContext]]] = {
    "agentic": get_context_via_agent,
}


async def retrieve_context_from_file(
    user_id: int,
    file_id: int,
    query: str,
    llm: BaseChatModel,
) -> RAGContext:
    """Retrieve context for a single file using the agentic retrieval method.

    Opens its own DB session so concurrent callers (asyncio.gather fan-out)
    do not share a session — AsyncSession is not concurrency-safe.

    Args:
        user_id: Owner of the file (row-level scope).
        file_id: File to retrieve context from.
        query: The user's natural-language query.
        llm: LangChain chat model used by the retrieval agent.

    Raises:
        DriveFileNotFoundError / RAGNotReadyError: file access/readiness failure.
        RAGRetrievalError: retrieval failed.
    """
    retrieval_fn = RETRIEVAL_REGISTRY["agentic"]
    async with session_scope() as file_session:
        return await retrieval_fn(file_session, user_id, file_id, query, llm)
