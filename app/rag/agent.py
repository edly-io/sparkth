"""LangGraph ReAct agent for agentic RAG search."""

from typing import Any, get_type_hints

from httpx import ConnectError, HTTPStatusError
from langchain.agents import create_agent
from langchain_core.exceptions import LangChainException
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from pydantic import BaseModel, Field, ValidationError, create_model

from app.core.config import get_settings
from app.core.logger import get_logger
from app.rag.exceptions import RAGRetrievalError
from app.rag.types import AgentSearchDecision
from app.rag.utils import get_asset

# Re-export for backwards-compatibility with modules that import from agent
__all__ = ["AgentSearchDecision", "run_agentic_rag_search"]

logger = get_logger(__name__)

_CONTEXT_KEYS = frozenset({"user_id", "file_id"})


class _SectionRef(BaseModel):
    chapter: str | None = None
    section: str | None = None
    subsection: str | None = None


class _SubmitAnswer(BaseModel):
    source_name: str = Field(description="The document's source_name from get_document_structure")
    selected_sections: list[_SectionRef] = Field(
        description="Sections to retrieve, matching values from get_document_structure exactly"
    )


def _make_submit_answer_tool() -> StructuredTool:
    """Return the response tool the agent must call to submit its final answer."""

    async def _noop(**_: Any) -> str:
        return "ok"

    return StructuredTool(
        name="submit_answer",
        description=(
            "Submit the final answer. Call this when you have determined which sections to retrieve. "
            "You MUST call this tool to complete your task."
        ),
        args_schema=_SubmitAnswer,
        coroutine=_noop,
    )


def _extract_decision(messages: list[Any]) -> AgentSearchDecision | None:
    """Find the last submit_answer tool call in the agent's message history."""
    for message in reversed(messages):
        tool_calls = getattr(message, "tool_calls", None)
        if not tool_calls:
            continue
        for tc in tool_calls:
            if tc.get("name") == "submit_answer":
                args = tc.get("args", {})
                return AgentSearchDecision(
                    source_name=args.get("source_name", ""),
                    selected_sections=args.get("selected_sections", []),
                )
    return None


def _bind_user_context(tools: list[Any], user_id: int, file_id: int) -> list[Any]:
    """Strip user_id/file_id from MCP tool input schemas and inject them on invocation.

    This keeps user context out of the system prompt and prevents the LLM from
    ever supplying or misusing these values.
    """
    result: list[Any] = []
    for tool in tools:
        schema = getattr(tool, "args_schema", None)
        if schema is None or not hasattr(schema, "model_fields"):
            result.append(tool)
            continue

        fields = schema.model_fields
        injected: dict[str, int] = {k: (user_id if k == "user_id" else file_id) for k in _CONTEXT_KEYS if k in fields}

        if not injected:
            result.append(tool)
            continue

        hints = get_type_hints(schema)
        reduced: dict[str, Any] = {
            name: (hints[name], field) for name, field in fields.items() if name not in _CONTEXT_KEYS
        }
        ReducedSchema: type[BaseModel] = create_model(f"{tool.name}_Input", **reduced)

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
        async with MultiServerMCPClient(
            {"rag-meta": {"url": rag_mcp_url, "transport": "http"}}  # type: ignore[misc, dict-item]
        ) as client:
            tools = await client.get_tools()
            tools = _bind_user_context(tools, user_id, file_id)
            tools = [*tools, _make_submit_answer_tool()]

            agent: Any = create_agent(llm, tools)

            prompt_template = get_asset("rag_search_agent_system_prompt", "txt")
            assert isinstance(prompt_template, str), "system prompt asset must be a string"
            system_message = SystemMessage(content=prompt_template)
            human_message = HumanMessage(content=user_query)

            result = await agent.ainvoke({"messages": [system_message, human_message]})

        decision = _extract_decision(result.get("messages", []))
        if decision is None:
            logger.warning("Agent did not call submit_answer for user %d, file %d", user_id, file_id)
            return AgentSearchDecision(source_name="", selected_sections=[])
        return decision

    except ValidationError as exc:
        logger.warning("submit_answer tool received invalid args for user %d, file %d: %s", user_id, file_id, exc)
        return AgentSearchDecision(source_name="", selected_sections=[])
    except (ConnectError, HTTPStatusError) as exc:
        logger.exception("MCP client connection error for user %s, file %s", user_id, file_id)
        raise RAGRetrievalError("Failed to connect to RAG metadata server: %s", exc) from exc
    except LangChainException as exc:
        logger.exception("Agent invocation error for user %s, file %s", user_id, file_id)
        raise RAGRetrievalError("Agent failed to process query: %s", exc) from exc
    except ValueError as exc:
        logger.exception("Error parsing agent response for user %s, file %s", user_id, file_id)
        raise RAGRetrievalError("Invalid agent response format: %s", exc) from exc
