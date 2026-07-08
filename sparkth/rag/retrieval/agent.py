"""Agentic RAG retrieval — LangGraph ReAct agent + orchestration for one document."""

from typing import Any

from langchain.agents import create_agent
from langchain_core.exceptions import LangChainException
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.errors import GraphRecursionError
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.log import get_logger
from sparkth.rag.config import get_rag_settings
from sparkth.rag.exceptions import RAGRetrievalError
from sparkth.rag.mcp.agent_tools import build_search_tools
from sparkth.rag.retrieval.utils import _lookup_document, format_chunks_as_context
from sparkth.rag.schemas import RAGSearchAgentResponse
from sparkth.rag.store import ChunkStoreService
from sparkth.rag.types import RAGContext
from sparkth.rag.utils import get_asset

logger = get_logger(__name__)


async def run_agentic_rag_retrieval(llm: Any, document_id: int, user_query: str) -> RAGSearchAgentResponse:
    """Run agentic RAG search to determine target sections.

    Args:
        llm: LangChain LLM instance to use for the agent
        document_id: Document ID to search within
        user_query: User's natural language query

    Returns:
        RAGSearchAgentResponse with source_name and selected_sections

    Raises:
        RAGRetrievalError: If a metadata query or agent invocation fails
    """
    try:
        agent_tools = build_search_tools(document_id)

        agent: Any = create_agent(
            model=llm, tools=agent_tools, response_format=RAGSearchAgentResponse, name="rag_search_agent"
        )

        prompt_template = get_asset("rag_search_agent_system_prompt", "txt")
        if not isinstance(prompt_template, str):
            raise TypeError("system prompt asset must be a string")
        system_message = SystemMessage(content=prompt_template)
        human_message = HumanMessage(content=user_query)

        result = await agent.ainvoke(
            {"messages": [system_message, human_message]},
            config={"recursion_limit": get_rag_settings().RAG_AGENT_MAX_RECURSION},
        )
        decision: RAGSearchAgentResponse | None = result.get("structured_response")
        if decision is None:
            logger.warning("Agent produced no structured_response for document %d", document_id)
            return RAGSearchAgentResponse(source_name="", selected_sections=[])
        return decision

    except ValidationError as exc:
        logger.exception("Agent response validation failed for document %d", document_id)
        raise RAGRetrievalError(f"Agent returned an invalid response structure: {exc}") from exc
    except GraphRecursionError as exc:
        logger.error(
            "RAG agent exceeded recursion limit (%d steps) for document %d",
            get_rag_settings().RAG_AGENT_MAX_RECURSION,
            document_id,
        )
        raise RAGRetrievalError("RAG agent exceeded maximum steps; query may be too complex.") from exc
    except LangChainException as exc:
        logger.exception("Agent invocation error for document %s", document_id)
        raise RAGRetrievalError(f"Agent failed to process query: {exc}") from exc


async def get_context_via_agent(
    session: AsyncSession,
    document_id: int,
    query: str,
    llm: Any,
    limit: int = get_rag_settings().RAG_DEFAULT_CHUNKS,
) -> RAGContext:
    """Retrieve RAG context for one document by agent-driven section selection.

    A LangGraph ReAct agent inspects the document structure via MCP tools,
    understands the user's intent, and hand-picks the relevant sections.
    All chunks in those sections are fetched directly — no similarity search.

    Raises:
        DocumentNotFoundError: Document not found or soft-deleted.
        RAGNotReadyError: Document exists but status is not READY.
        RAGRetrievalError: Agent invocation or section fetch failed.
    """
    store = ChunkStoreService()
    document = await _lookup_document(session, document_id)
    source_name = document.name

    if not query.strip():
        query = source_name

    logger.info(
        "RAG retrieval via agent: document_id=%d source_name=%s query_len=%d",
        document_id,
        source_name,
        len(query),
    )

    decision = await run_agentic_rag_retrieval(llm, document_id, query)

    logger.info(
        "RAG agent selected %d section(s) for document_id=%d",
        len(decision.selected_sections),
        document_id,
    )

    try:
        results = await store.fetch_chunks_by_sections(
            session,
            document_id,
            [s.model_dump() for s in decision.selected_sections],
            limit,
        )
    except SQLAlchemyError as exc:
        logger.error("Section fetch failed for document_id=%d: %s", document_id, exc)
        raise RAGRetrievalError(f"Section fetch failed: {exc}") from exc

    logger.info("RAG: found %d chunks for document_id=%d via agent", len(results), document_id)
    logger.info(
        "RAG chunk IDs in context for document_id=%d: %s",
        document_id,
        [chunk.id for chunk in results],
    )

    return RAGContext(
        document_id=document_id,
        source_name=source_name,
        chunks=results,
        formatted_text=format_chunks_as_context(source_name, results),
    )
