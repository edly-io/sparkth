"""Agentic RAG retrieval — LangGraph ReAct agent + orchestration for one file."""

from typing import Any

from langchain.agents import create_agent
from langchain_core.exceptions import LangChainException
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.errors import GraphRecursionError
from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.lib.log import get_logger
from app.rag.config import get_rag_settings
from app.rag.exceptions import RAGRetrievalError
from app.rag.mcp.agent_tools import build_search_tools
from app.rag.retrieval.utils import _lookup_drive_file, format_chunks_as_context
from app.rag.schemas import RAGSearchAgentResponse
from app.rag.store import ChunkStoreService
from app.rag.types import RAGContext
from app.rag.utils import get_asset, resolve_source_name

logger = get_logger(__name__)


async def run_agentic_rag_retrieval(llm: Any, user_id: int, file_id: int, user_query: str) -> RAGSearchAgentResponse:
    """Run agentic RAG search to determine target sections.

    Args:
        llm: LangChain LLM instance to use for the agent
        user_id: User ID for row-level scoping
        file_id: File ID to search within
        user_query: User's natural language query

    Returns:
        RAGSearchAgentResponse with source_name and selected_sections

    Raises:
        RAGRetrievalError: If a metadata query or agent invocation fails
    """
    try:
        agent_tools = build_search_tools(user_id, file_id)

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
            logger.warning("Agent produced no structured_response for user %d, file %d", user_id, file_id)
            return RAGSearchAgentResponse(source_name="", selected_sections=[])
        return decision

    except ValidationError as exc:
        logger.exception("Agent response validation failed for user %d, file %d", user_id, file_id)
        raise RAGRetrievalError(f"Agent returned an invalid response structure: {exc}") from exc
    except GraphRecursionError as exc:
        logger.error(
            "RAG agent exceeded recursion limit (%d steps) for user %d, file %d",
            get_rag_settings().RAG_AGENT_MAX_RECURSION,
            user_id,
            file_id,
        )
        raise RAGRetrievalError("RAG agent exceeded maximum steps; query may be too complex.") from exc
    except LangChainException as exc:
        logger.exception("Agent invocation error for user %s, file %s", user_id, file_id)
        raise RAGRetrievalError(f"Agent failed to process query: {exc}") from exc


async def get_context_via_agent(
    session: AsyncSession,
    user_id: int,
    file_db_id: int,
    query: str,
    llm: Any,
    limit: int = get_rag_settings().RAG_DEFAULT_CHUNKS,
) -> RAGContext:
    """Retrieve RAG context for one file by agent-driven section selection.

    A LangGraph ReAct agent inspects the document structure via MCP tools,
    understands the user's intent, and hand-picks the relevant sections.
    All chunks in those sections are fetched directly — no similarity search.

    Raises:
        DriveFileNotFoundError: File not found or not owned by user.
        RAGNotReadyError: File exists but rag_status is not READY.
        RAGRetrievalError: Agent invocation or section fetch failed.
    """
    store = ChunkStoreService()
    drive_file = await _lookup_drive_file(session, user_id, file_db_id)
    source_name = resolve_source_name(drive_file)

    if not query.strip():
        query = source_name

    logger.info(
        "RAG retrieval via agent: user=%d file_db_id=%d source_name=%s query_len=%d",
        user_id,
        file_db_id,
        source_name,
        len(query),
    )

    decision = await run_agentic_rag_retrieval(llm, user_id, file_db_id, query)

    logger.info(
        "RAG agent selected %d section(s) for file_db_id=%d",
        len(decision.selected_sections),
        file_db_id,
    )

    try:
        results = await store.fetch_chunks_by_sections(
            session,
            user_id,
            source_name,
            [s.model_dump() for s in decision.selected_sections],
            limit,
        )
    except Exception as exc:
        logger.error("Section fetch failed for file_db_id=%d: %s", file_db_id, exc)
        raise RAGRetrievalError(f"Section fetch failed: {exc}") from exc

    logger.info("RAG: found %d chunks for file_db_id=%d via agent", len(results), file_db_id)
    logger.info(
        "RAG chunk IDs in context for file_db_id=%d: %s",
        file_db_id,
        [r.chunk.id for r in results],
    )

    return RAGContext(
        file_db_id=file_db_id,
        source_name=source_name,
        chunks=results,
        formatted_text=format_chunks_as_context(source_name, results),
    )
