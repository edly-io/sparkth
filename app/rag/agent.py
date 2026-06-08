"""LangGraph ReAct agent for agentic RAG search."""

from typing import Any

from langchain.agents import create_agent
from langchain_core.exceptions import LangChainException
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.errors import GraphRecursionError
from pydantic import ValidationError

from app.lib.log import get_logger
from app.rag.constants import AGENT_MAX_RECURSION
from app.rag.exceptions import RAGRetrievalError
from app.rag.mcp.agent_tools import build_search_tools
from app.rag.types import RAGSearchAgentResponse
from app.rag.utils import get_asset

logger = get_logger(__name__)


class RAGSearchAgent:
    """LangGraph ReAct agent encapsulating agentic RAG section search."""

    async def search(self, llm: Any, user_id: int, file_id: int, user_query: str) -> RAGSearchAgentResponse:
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
                config={"recursion_limit": AGENT_MAX_RECURSION},
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
                AGENT_MAX_RECURSION,
                user_id,
                file_id,
            )
            raise RAGRetrievalError("RAG agent exceeded maximum steps; query may be too complex.") from exc
        except LangChainException as exc:
            logger.exception("Agent invocation error for user %s, file %s", user_id, file_id)
            raise RAGRetrievalError(f"Agent failed to process query: {exc}") from exc
