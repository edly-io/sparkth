"""LangGraph ReAct agent for agentic RAG search."""

import json
from dataclasses import dataclass
from typing import Any

from httpx import ConnectError, HTTPStatusError
from langchain_core.exceptions import LangChainException
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

from app.core.config import get_settings
from app.core.logger import get_logger
from app.rag.exceptions import RAGRetrievalError

logger = get_logger(__name__)


@dataclass
class AgentSearchDecision:
    """Agent's decision about which sections to fetch directly."""

    source_name: str
    selected_sections: list[dict[str, str | None]]


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
        client = MultiServerMCPClient({"rag-meta": {"url": rag_mcp_url, "transport": "http"}})  # type: ignore[misc, dict-item]
        tools = await client.get_tools()

        # Create ReAct agent with the MCP tools
        graph = create_react_agent(llm, tools)

        # Build system and human messages
        system_message = SystemMessage(
            content=(
                "You are a document retrieval agent. Your job is to understand the user's intent "
                "and hand-pick the exact sections of a document that contain the relevant content. "
                "Use get_document_structure to see the full ordered structure of the document "
                "(chapters, sections, subsections, chunk counts, and position_index). "
                "Use search_section_by_keyword if you need to locate sections by name. "
                "Reason about positional references (e.g. 'second half' means sections whose "
                "position_index is >= half the total section count). "
                "Return ONLY a JSON object with two keys: "
                "'source_name' (str, the file's source_name from get_document_structure or get_file_metadata) and "
                "'selected_sections' (list of objects, each with 'chapter', 'section', 'subsection' keys "
                "matching exactly the values returned by get_document_structure — use null for missing fields). "
                "Do NOT include any explanation. Return ONLY the JSON object. "
                f"User ID: {user_id}. File ID: {file_id}."
            )
        )

        human_message = HumanMessage(content=user_query)

        # Invoke the agent
        result = await graph.ainvoke({"messages": [system_message, human_message]})

        # Extract the final message
        if "messages" not in result or not result["messages"]:
            logger.warning("Agent returned no messages for user %s, file %s", user_id, file_id)
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
            logger.warning(
                "Failed to parse agent response for user %s, file %s: %s",
                user_id,
                file_id,
                exc,
            )
            return AgentSearchDecision(source_name="", selected_sections=[])

    except (ConnectError, HTTPStatusError) as exc:
        logger.exception("MCP client connection error for user %s, file %s", user_id, file_id)
        raise RAGRetrievalError(f"Failed to connect to RAG metadata server: {exc}") from exc
    except LangChainException as exc:
        logger.exception("Agent invocation error for user %s, file %s", user_id, file_id)
        raise RAGRetrievalError(f"Agent failed to process query: {exc}") from exc
    except ValueError as exc:
        logger.exception("Error parsing agent response for user %s, file %s", user_id, file_id)
        raise RAGRetrievalError(f"Invalid agent response format: {exc}") from exc
