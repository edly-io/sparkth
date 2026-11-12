"""The planner's middleware: one tool call per reply, refused calls back to the planner, and a call limit."""

from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware import AgentState, ToolCallRequest, after_model, wrap_tool_call
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import Command

from sparkth.lib.audit.events import AuditModelInfo
from sparkth.lib.i18n import gettext
from sparkth.lib.log import get_logger
from sparkth.plugins.compose.constants import (
    PLANNER_REFUSED_CALL_LIMIT,
    PLANNER_TOOL_CALL_LIMIT,
    TOOL_CALL_LIMIT_NOTICE,
)

logger = get_logger(__name__)


@after_model(name="first_hand_off_only")
def first_hand_off_only(state: AgentState[Any], runtime: Runtime[AuditModelInfo]) -> dict[str, Any] | None:
    """Keep only the first tool call of a planner reply, so one hand-off or operation runs at a time."""
    reply = state["messages"][-1]
    if not (isinstance(reply, AIMessage) and len(reply.tool_calls) > 1):
        return None
    logger.warning("Planner asked for %d tool calls in one reply; only the first runs", len(reply.tool_calls))
    return {"messages": [reply.model_copy(update={"tool_calls": reply.tool_calls[:1]})]}


@wrap_tool_call
async def bounce_refused_calls(
    request: ToolCallRequest, handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]]
) -> ToolMessage | Command[Any]:
    """Send a call its tool refused (such as a hand-off without its request) back to the planner.

    A hand-off ends the run with its result, so without this the refusal itself would be the reply.
    """
    result = await handler(request)
    if isinstance(result, ToolMessage) and result.status == "error":
        logger.warning("Planner's call to '%s' was refused; asking it again", request.tool_call["name"])
        return Command(goto="model", update={"messages": [result]})
    return result


@after_model(can_jump_to=["end"], name="stop_after_too_many_calls")
def stop_after_too_many_calls(state: AgentState[Any], runtime: Runtime[AuditModelInfo]) -> dict[str, Any] | None:
    """End the run with the tool-call limit notice once the planner asks for more than
    ``PLANNER_TOOL_CALL_LIMIT`` calls in it, or more than ``PLANNER_REFUSED_CALL_LIMIT`` of its calls
    were refused.

    A refused call does not count against the call limit, so a planner that fixes its call still
    gets to finish the turn.
    """
    reply = state["messages"][-1]
    if not (isinstance(reply, AIMessage) and reply.tool_calls):
        return None
    refused = sum(1 for message in state["messages"] if isinstance(message, ToolMessage) and message.status == "error")
    calls = sum(len(message.tool_calls) for message in state["messages"] if isinstance(message, AIMessage)) - refused
    if calls <= PLANNER_TOOL_CALL_LIMIT and refused <= PLANNER_REFUSED_CALL_LIMIT:
        return None
    logger.warning(
        "Planner asked for %d tool calls (limit %d) and had %d refused (limit %d); the turn ends with a notice",
        calls,
        PLANNER_TOOL_CALL_LIMIT,
        refused,
        PLANNER_REFUSED_CALL_LIMIT,
    )
    return {"jump_to": "end", "messages": [AIMessage(content=gettext(TOOL_CALL_LIMIT_NOTICE))]}
