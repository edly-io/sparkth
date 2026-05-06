"""LangGraph ReAct agent for agentic RAG search."""

from typing import Any

from httpx import ConnectError, HTTPStatusError
from langchain.agents import create_agent
from langchain_core.exceptions import LangChainException
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.sessions import StreamableHttpConnection
from pydantic import BaseModel, Field, ValidationError, create_model

from app.core.config import get_settings
from app.core.logger import get_logger
from app.rag.exceptions import RAGRetrievalError
from app.rag.types import RAGSearchAgentResponse
from app.rag.utils import get_asset

# Re-export for backwards-compatibility with modules that import from agent
__all__ = ["run_agentic_rag_search"]

logger = get_logger(__name__)

_CONTEXT_KEYS = frozenset({"user_id", "file_id"})

_JSON_TYPE_MAP: dict[str, type] = {
    "integer": int,
    "string": str,
    "number": float,
    "boolean": bool,
}


def _bind_user_context(tools: list[Any], user_id: int, file_id: int) -> list[Any]:
    """Strip user_id/file_id from MCP tool input schemas and inject them on invocation.

    Uses tool.args (LangChain's stable JSON-schema property) rather than
    args_schema.model_fields so this works reliably with MCP adapter tools.
    """
    result: list[Any] = []
    for tool in tools:
        try:
            tool_arg_names = set((tool.args or {}).keys())
        except (AttributeError, TypeError):
            result.append(tool)
            continue

        injected: dict[str, int] = {
            k: (user_id if k == "user_id" else file_id) for k in _CONTEXT_KEYS if k in tool_arg_names
        }

        if not injected:
            result.append(tool)
            continue

        remaining = {k: v for k, v in tool.args.items() if k not in _CONTEXT_KEYS}
        field_defs: dict[str, Any] = {
            name: (
                _JSON_TYPE_MAP.get(schema.get("type", "string"), Any),
                Field(description=schema.get("description", name)),
            )
            for name, schema in remaining.items()
        }
        ReducedSchema: type[BaseModel] = create_model(f"{tool.name}_Input", **field_defs)

        async def _coroutine(_t: Any = tool, _ctx: dict[str, int] = injected, **kwargs: Any) -> Any:
            return await _t.ainvoke({**kwargs, **_ctx})

        result.append(
            StructuredTool(
                name=tool.name,
                description=tool.description,
                args_schema=ReducedSchema,
                coroutine=_coroutine,
            )
        )
    return result


async def run_agentic_rag_search(llm: Any, user_id: int, file_id: int, user_query: str) -> RAGSearchAgentResponse:
    """Run agentic RAG search to determine target sections.

    Args:
        llm: LangChain LLM instance to use for the agent
        user_id: User ID for row-level scoping
        file_id: File ID to search within
        user_query: User's natural language query

    Returns:
        RAGSearchAgentResponse with source_name and selected_sections

    Raises:
        RAGRetrievalError: If MCP client connection or agent invocation fails
    """
    rag_mcp_url = get_settings().RAG_MCP_URL

    try:
        client = MultiServerMCPClient(
            {"rag-meta": StreamableHttpConnection(url=rag_mcp_url, transport="streamable_http")}
        )
        tools = await client.get_tools()
        tools = _bind_user_context(tools, user_id, file_id)

        agent: Any = create_agent(
            model=llm, tools=tools, response_format=RAGSearchAgentResponse, name="rag_search_agent"
        )

        prompt_template = get_asset("rag_search_agent_system_prompt", "txt")
        if not isinstance(prompt_template, str):
            raise TypeError("system prompt asset must be a string")
        system_message = SystemMessage(content=prompt_template)
        human_message = HumanMessage(content=user_query)

        result = await agent.ainvoke({"messages": [system_message, human_message]})
        decision: RAGSearchAgentResponse | None = result.get("structured_response")
        if decision is None:
            logger.warning("Agent produced no structured_response for user %d, file %d", user_id, file_id)
            return RAGSearchAgentResponse(source_name="", selected_sections=[])
        return decision

    except ValidationError as exc:
        logger.warning("Agent response validation failed for user %d, file %d: %s", user_id, file_id, exc)
        return RAGSearchAgentResponse(source_name="", selected_sections=[])
    except (ConnectError, HTTPStatusError) as exc:
        logger.exception("MCP client connection error for user %s, file %s", user_id, file_id)
        raise RAGRetrievalError(f"Failed to connect to RAG metadata server: {exc}") from exc
    except LangChainException as exc:
        logger.exception("Agent invocation error for user %s, file %s", user_id, file_id)
        raise RAGRetrievalError(f"Agent failed to process query: {exc}") from exc
    except ValueError as exc:
        logger.exception("Error parsing agent response for user %s, file %s", user_id, file_id)
        raise RAGRetrievalError(f"Invalid agent response format: {exc}") from exc
