"""The planner's middleware: one call per reply, a limit on steps, a limit on rejected calls, no
repeat hand-off and no step after an agent's choices."""

from typing import Any

from langchain.agents.middleware import AgentState, after_model, before_model
from langchain_core.messages import AIMessage, AnyMessage, ToolCall, ToolMessage
from langgraph.runtime import Runtime

from sparkth.lib.audit.events import AuditModelInfo
from sparkth.lib.compose.constants import OPERATOR_AGENT_NAME
from sparkth.lib.i18n import gettext
from sparkth.lib.log import get_logger
from sparkth.plugins.compose.constants import MAX_REJECTED_PLANNER_CALLS, MAX_STEPS_PER_TURN, STOPPED_EARLY_NOTICE

logger = get_logger(__name__)

# The lines that open a block of choices in a reply.
_CHOICES_FENCES = ("```options", "```options single")


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


def _step_results(messages: list[AnyMessage]) -> list[ToolMessage]:
    """One result per step the turn has run, in order. Rejected calls come back as errors and are left out."""
    return [message for message in messages if isinstance(message, ToolMessage) and message.status != "error"]


@after_model(can_jump_to=["end"], name="enforce_step_limit")
def enforce_step_limit(state: AgentState[Any], runtime: Runtime[AuditModelInfo]) -> dict[str, Any] | None:
    """End the turn with the limit notice when the planner asks for another call after the turn's
    max number of steps has run."""
    reply = state["messages"][-1]
    if not (isinstance(reply, AIMessage) and reply.tool_calls):
        return None
    steps_run = len(_step_results(state["messages"]))
    if steps_run >= MAX_STEPS_PER_TURN:
        logger.warning(
            "Planner asked for another call after %d steps (limit %d); the turn ends with a notice",
            steps_run,
            MAX_STEPS_PER_TURN,
        )
        return {"jump_to": "end", "messages": [AIMessage(content=gettext(STOPPED_EARLY_NOTICE))]}
    return None


@after_model(name="no_repeat_hand_off")
def no_repeat_hand_off(state: AgentState[Any], runtime: Runtime[AuditModelInfo]) -> dict[str, Any] | None:
    """End the turn as it stands when the planner hands off again to the agent that has just answered.

    The author has just read that agent's reply, often a question for them. The operator may run
    twice in a row: the author never reads its text.
    """
    reply = state["messages"][-1]
    if not (isinstance(reply, AIMessage) and reply.tool_calls):
        return None
    step_results = _step_results(state["messages"])
    next_agent = reply.tool_calls[0]["name"]
    if next_agent != OPERATOR_AGENT_NAME and step_results and step_results[-1].name == next_agent:
        logger.warning("Planner handed off to '%s' again right after its reply; the turn ends there", next_agent)
        return {"messages": [_with_calls(reply, [])]}
    return None


@after_model(can_jump_to=["end"], name="enforce_rejected_call_limit")
def enforce_rejected_call_limit(state: AgentState[Any], runtime: Runtime[AuditModelInfo]) -> dict[str, Any] | None:
    """End the turn, telling the author it could not finish, when the planner asks for another call
    after more of its calls were rejected than a turn allows. A call is rejected when it names no
    tool the planner has or its arguments don't fit the tool. Nothing ran, so it is not a step, and
    a planner that fixes its call still gets to finish the turn."""
    reply = state["messages"][-1]
    if not (isinstance(reply, AIMessage) and reply.tool_calls):
        return None
    rejected = sum(1 for message in state["messages"] if isinstance(message, ToolMessage) and message.status == "error")
    if rejected > MAX_REJECTED_PLANNER_CALLS:
        logger.warning(
            "Planner asked for another call after %d rejected calls (limit %d); the turn ends with a notice",
            rejected,
            MAX_REJECTED_PLANNER_CALLS,
        )
        return {
            "jump_to": "end",
            "messages": [
                AIMessage(
                    content=gettext("Something went wrong and I couldn't finish this. Please send your message again.")
                )
            ],
        }
    return None


def _ends_with_choices(reply: str) -> bool:
    """Whether ``reply`` ends with a block of choices for the author, closed or left open."""
    lines = [line.strip() for line in reply.splitlines()]
    opening_fences = [index for index, line in enumerate(lines) if line in _CHOICES_FENCES]
    if not opening_fences:
        return False
    # The block starts after the last opening fence.
    block = lines[opening_fences[-1] + 1 :]
    close = block.index("```") if "```" in block else len(block)
    return any(block[:close]) and not any(block[close + 1 :])


@before_model(can_jump_to=["end"], name="no_step_after_choices")
def no_step_after_choices(state: AgentState[Any], runtime: Runtime[AuditModelInfo]) -> dict[str, Any] | None:
    """End the turn as it stands, without asking the planner, when an agent's reply ended with
    choices for the author.

    The author answers them before anything else runs. An operation's result never ends the turn:
    the author never reads the operator's text.
    """
    # The result of a step that has just run, when the last message is one.
    just_ran = _step_results(state["messages"][-1:])
    if not just_ran or just_ran[0].name == OPERATOR_AGENT_NAME:
        return None
    if _ends_with_choices(just_ran[0].artifact or ""):
        logger.info("Agent '%s' offered the author choices; the turn ends there", just_ran[0].name)
        return {"jump_to": "end"}
    return None
