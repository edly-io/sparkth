"""The planner's middleware: one tool call per reply, and limits on steps and refused calls."""

from typing import Any

from langchain.agents.middleware import AgentState, after_model
from langchain_core.messages import AIMessage, ToolCall, ToolMessage
from langgraph.runtime import Runtime

from sparkth.lib.audit.events import AuditModelInfo
from sparkth.lib.compose.constants import OPERATOR_TOOL_NAME
from sparkth.lib.i18n import gettext
from sparkth.lib.log import get_logger
from sparkth.plugins.compose.constants import MAX_STEPS_PER_TURN, PLANNER_REFUSED_CALL_LIMIT, TOOL_CALL_LIMIT_NOTICE

logger = get_logger(__name__)


def _with_calls(reply: AIMessage, kept: list[ToolCall]) -> AIMessage:
    """``reply`` asking only for the ``kept`` tool calls.

    Some providers repeat each call as a block of the reply's content and reject a call that gets
    no result, so the blocks of the calls left out go too.
    """
    kept_ids = {call["id"] for call in kept}
    content: str | list[str | dict[str, Any]] = reply.content
    if isinstance(content, list):
        content = [
            block
            for block in content
            if not (isinstance(block, dict) and block.get("type") == "tool_use" and block.get("id") not in kept_ids)
        ]
    return reply.model_copy(update={"tool_calls": kept, "content": content})


@after_model(name="first_hand_off_only")
def first_hand_off_only(state: AgentState[Any], runtime: Runtime[AuditModelInfo]) -> dict[str, Any] | None:
    """Keep only the first tool call of a planner reply, so one step runs at a time."""
    reply = state["messages"][-1]
    if not (isinstance(reply, AIMessage) and len(reply.tool_calls) > 1):
        return None
    logger.warning("Planner asked for %d tool calls in one reply; only the first runs", len(reply.tool_calls))
    return {"messages": [_with_calls(reply, reply.tool_calls[:1])]}


@after_model(can_jump_to=["end"], name="limit_steps")
def limit_steps(state: AgentState[Any], runtime: Runtime[AuditModelInfo]) -> dict[str, Any] | None:
    """Keep a turn from running on: end it at its limit of steps or of refused calls, and never run
    the agent that has just answered again.

    A step is a call that ran, an agent's or the operator's work; a call its tool refused is not
    one. Once ``MAX_STEPS_PER_TURN`` steps have run, or more than ``PLANNER_REFUSED_CALL_LIMIT`` calls
    were refused, a planner that asks for another call ends the turn with the limit notice. A
    hand-off to the agent whose reply the author has just read ends the turn as it stands.
    """
    reply = state["messages"][-1]
    if not (isinstance(reply, AIMessage) and reply.tool_calls):
        return None
    results = [message for message in state["messages"] if isinstance(message, ToolMessage)]
    steps = [result for result in results if result.status != "error"]
    refused = len(results) - len(steps)
    if len(steps) >= MAX_STEPS_PER_TURN or refused > PLANNER_REFUSED_CALL_LIMIT:
        logger.warning(
            "Planner asked for another call after %d steps (limit %d) and %d refused calls (limit %d); "
            "the turn ends with a notice",
            len(steps),
            MAX_STEPS_PER_TURN,
            refused,
            PLANNER_REFUSED_CALL_LIMIT,
        )
        return {"jump_to": "end", "messages": [AIMessage(content=gettext(TOOL_CALL_LIMIT_NOTICE))]}
    asked_for = reply.tool_calls[0]["name"]
    if steps and steps[-1].name == asked_for != OPERATOR_TOOL_NAME:
        logger.warning("Planner handed off to '%s' again right after its reply; the turn ends there", asked_for)
        return {"messages": [_with_calls(reply, [])]}
    return None
