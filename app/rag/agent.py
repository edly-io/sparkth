"""LangGraph ReAct agent for agentic RAG search."""

import json
from typing import Any

from httpx import ConnectError, HTTPStatusError
from langchain_core.exceptions import LangChainException
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

from app.core.config import get_settings
from app.core.logger import get_logger
from app.rag.exceptions import RAGRetrievalError
from app.rag.types import AgentSearchDecision
from app.rag.utils import get_asset

# Re-export for backwards-compatibility with modules that import from agent
__all__ = ["AgentSearchDecision", "run_agentic_rag_search"]

logger = get_logger(__name__)


async def run_agentic_rag_search(llm: Any, user_id: int, file_id: int, user_query: str) -> AgentSearchDecision:
    """Run agentic RAG search to determine target sections.

    Args:
        llm: LangChain LLM instance to use for the agent
        user_id: User ID for row-level scoping
        file_id: File ID to search within
        user_query: User's natural language query

    Returns:
        AgentSearchDecision with source_name and target_sections

    Raises:
        RAGRetrievalError: If MCP client connection or agent invocation fails
    """
    rag_mcp_url = get_settings().RAG_MCP_URL

    try:
        client = MultiServerMCPClient(
            {"rag-meta": {"url": rag_mcp_url, "transport": "http"}}  # type: ignore[misc, dict-item]
        )
        tools = await client.get_tools()

        # Create ReAct agent with the MCP tools
        agent = create_react_agent(llm, tools)

        # Build system and human messages
        prompt_template = get_asset("rag_search_agent_system_prompt", "txt")
        assert isinstance(prompt_template, str), "system prompt asset must be a string"
        system_message = SystemMessage(content=prompt_template.format(user_id=user_id, file_id=file_id))
        human_message = HumanMessage(content=user_query)

        # Invoke the agent
        result = await agent.ainvoke({"messages": [system_message, human_message]})

        # Extract the final message
        if "messages" not in result or not result["messages"]:
            logger.warning(f"Agent returned no messages for user {user_id}, file {file_id}")
            return AgentSearchDecision(source_name="", selected_sections=[])

        final_message = result["messages"][-1]

        # Parse the JSON from the final message
        try:
            content = final_message.content
            # Strip markdown code fences if the model wraps the JSON
            if "```" in content:
                content = content.split("```")[-2].removeprefix("json").strip()
            decision_data = json.loads(content)
            source_name = decision_data.get("source_name", "")
            selected_sections = decision_data.get("selected_sections", [])

            return AgentSearchDecision(source_name=source_name, selected_sections=selected_sections)
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.warning(f"Failed to parse agent response for user {user_id}, file {file_id}: {exc}")
            return AgentSearchDecision(source_name="", selected_sections=[])

    except (ConnectError, HTTPStatusError) as exc:
        logger.exception(f"MCP client connection error for user {user_id}, file {file_id}")
        raise RAGRetrievalError(f"Failed to connect to RAG metadata server: {exc}") from exc
    except LangChainException as exc:
        logger.exception(f"Agent invocation error for user {user_id}, file {file_id}")
        raise RAGRetrievalError(f"Agent failed to process query: {exc}") from exc
    except ValueError as exc:
        logger.exception(f"Error parsing agent response for user {user_id}, file {file_id}")
        raise RAGRetrievalError(f"Invalid agent response format: {exc}") from exc
