"""Middleware that trims a planner reply or ends the turn early: one call per reply, a limit on steps,
a limit on rejected calls, no repeat hand-off and no step after an agent's choices."""

from collections.abc import Sequence
from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState, after_model, before_model
from langchain_core.messages import AIMessage, AnyMessage, ToolMessage
from langgraph.runtime import Runtime

from sparkth.lib.audit.events import AuditModelInfo
from sparkth.lib.compose.constants import OPERATOR_AGENT_NAME
from sparkth.lib.i18n import gettext
from sparkth.lib.log import get_logger
from sparkth.plugins.compose.constants import (
    MAX_REJECTED_PLANNER_CALLS,
    MAX_STEPS_PER_TURN,
    STOPPED_EARLY_NOTICE,
)
from sparkth.plugins.compose.enums import TurnEventType
from sparkth.plugins.compose.lib.enums import OptionsFence
from sparkth.plugins.compose.planner.middleware.messages import get_step_number, get_step_results, with_calls
from sparkth.plugins.compose.planner.middleware.plan import get_plan, get_rejection_reason
from sparkth.plugins.compose.planner.types import ExistingPlan, PlannedStep

logger = get_logger(__name__)

# The lines that open a block of choices in a reply.
_CHOICES_FENCES = tuple(f"```{fence}" for fence in OptionsFence)


@after_model(name="first_hand_off_only")
def first_hand_off_only(state: AgentState[Any], runtime: Runtime[AuditModelInfo]) -> dict[str, Any] | None:
    """Keep only the first tool call of a planner reply, so one step runs at a time."""
    reply = state["messages"][-1]
    if not (isinstance(reply, AIMessage) and len(reply.tool_calls) > 1):
        return None
    logger.warning("Planner asked for %d tool calls in one reply; only the first runs", len(reply.tool_calls))
    return {"messages": [with_calls(reply, reply.tool_calls[:1])]}


def _build_paused_plan_message(steps: Sequence[PlannedStep], done: int) -> str:
    """What the author reads when a turn stops at its limit with steps of its plan left: the first
    ``done`` tasks as done, the rest as left, and the choice to carry on or stop."""
    tasks = [f"{number}. {step.task}" for number, step in enumerate(steps, start=1)]
    choices = [f"```{OptionsFence.SINGLE}", gettext("Continue"), gettext("Stop here"), "```"]
    return "\n\n".join(
        [
            gettext("I've paused here so you can check the work so far."),
            gettext("Done:"),
            "\n".join(tasks[:done]),
            gettext("Still to do:"),
            "\n".join(tasks[done:]),
            "\n".join([gettext("Shall I continue with the rest?"), *choices]),
        ]
    )


def _get_turn_ending_response(
    messages: list[AnyMessage],
    reply: AIMessage,
    existing_plan: ExistingPlan | None,
    runtime: Runtime[AuditModelInfo],
    notice: str,
) -> dict[str, Any]:
    """What a limit hook returns to end the turn in place of the call ``reply`` asks for.

    When that call is for the next step of the plan the turn follows, after at least one step ran,
    the turn ends with what is done, what is left and the offer to continue, and the plan is
    reported as waiting at that step: not run, which is where the next message continues from.
    Otherwise the turn ends with ``notice``.
    """
    call = reply.tool_calls[0]
    number = get_step_number(call)
    plan = get_plan(messages, existing_plan, number)
    if plan is not None and number is not None and get_step_results(messages):
        if get_rejection_reason(call["name"], number, plan) is None:
            runtime.stream_writer({"type": TurnEventType.PLAN_STEP, "number": number, "ran": False})
            return {
                "jump_to": "end",
                "messages": [AIMessage(content=_build_paused_plan_message(plan.steps, number - 1))],
            }
    return {"jump_to": "end", "messages": [AIMessage(content=notice)]}


def enforce_step_limit(existing_plan: ExistingPlan | None) -> AgentMiddleware[Any, Any, Any]:
    """Middleware that ends the turn when the planner asks for another call after the turn's max
    number of steps has run. ``existing_plan`` is a plan from an earlier message that isn't finished."""

    @after_model(can_jump_to=["end"], name="enforce_step_limit")
    def enforce_step_limit(state: AgentState[Any], runtime: Runtime[AuditModelInfo]) -> dict[str, Any] | None:
        messages = state["messages"]
        reply = messages[-1]
        if not (isinstance(reply, AIMessage) and reply.tool_calls):
            return None
        steps_run = len(get_step_results(messages))
        if steps_run < MAX_STEPS_PER_TURN:
            return None
        logger.warning(
            "Planner asked for another call after %d steps (limit %d); the turn ends there",
            steps_run,
            MAX_STEPS_PER_TURN,
        )
        return _get_turn_ending_response(messages, reply, existing_plan, runtime, gettext(STOPPED_EARLY_NOTICE))

    return enforce_step_limit


def enforce_rejected_call_limit(existing_plan: ExistingPlan | None) -> AgentMiddleware[Any, Any, Any]:
    """Middleware that ends the turn when the planner asks for another call after more of its calls
    were rejected than a turn allows. ``existing_plan`` is a plan from an earlier message that isn't
    finished.

    A call is rejected when it names no tool the planner has, its arguments don't fit the tool, or
    it doesn't fit the plan. Nothing ran, so it is not a step, and a planner that fixes its call
    still gets to finish the turn.
    """

    @after_model(can_jump_to=["end"], name="enforce_rejected_call_limit")
    def enforce_rejected_call_limit(state: AgentState[Any], runtime: Runtime[AuditModelInfo]) -> dict[str, Any] | None:
        messages = state["messages"]
        reply = messages[-1]
        if not (isinstance(reply, AIMessage) and reply.tool_calls):
            return None
        rejected = sum(1 for message in messages if isinstance(message, ToolMessage) and message.status == "error")
        if rejected <= MAX_REJECTED_PLANNER_CALLS:
            return None
        logger.warning(
            "Planner asked for another call after %d rejected calls (limit %d); the turn ends there",
            rejected,
            MAX_REJECTED_PLANNER_CALLS,
        )
        could_not_finish = gettext("Something went wrong and I couldn't finish this. Please send your message again.")
        return _get_turn_ending_response(messages, reply, existing_plan, runtime, could_not_finish)

    return enforce_rejected_call_limit


def end_at_repeat_hand_off(existing_plan: ExistingPlan | None) -> AgentMiddleware[Any, Any, Any]:
    """Middleware that ends the turn as it stands when the planner hands off again to the agent that
    has just answered. ``existing_plan`` is a plan from an earlier message that isn't finished.

    The author has just read that agent's reply, often a question for them. The operator may run
    twice in a row: the author never reads its text. A turn that follows a plan is left alone: there
    the same agent may do two steps in a row.
    """

    @after_model(name="end_at_repeat_hand_off")
    def end_on_a_repeat(state: AgentState[Any], runtime: Runtime[AuditModelInfo]) -> dict[str, Any] | None:
        messages = state["messages"]
        reply = messages[-1]
        if not (isinstance(reply, AIMessage) and reply.tool_calls):
            return None
        call = reply.tool_calls[0]
        if get_plan(messages, existing_plan, get_step_number(call)) is not None:
            return None
        step_results = get_step_results(messages)
        next_agent = call["name"]
        if next_agent != OPERATOR_AGENT_NAME and step_results and step_results[-1].name == next_agent:
            logger.warning("Planner handed off to '%s' again right after its reply; the turn ends there", next_agent)
            return {"messages": [with_calls(reply, [])]}
        return None

    return end_on_a_repeat


def _agent_reply_ends_with_choices(reply: str) -> bool:
    """Whether ``reply`` ends with a block of choices for the author, closed or left open."""
    lines = [line.strip() for line in reply.splitlines()]
    opening_fences = [index for index, line in enumerate(lines) if line in _CHOICES_FENCES]
    if not opening_fences:
        return False
    # The block starts after the last opening fence.
    block = lines[opening_fences[-1] + 1 :]
    close = block.index("```") if "```" in block else len(block)
    return any(block[:close]) and not any(block[close + 1 :])


@before_model(can_jump_to=["end"], name="end_turn_after_agent_offers_choices")
def end_turn_after_agent_offers_choices(
    state: AgentState[Any], runtime: Runtime[AuditModelInfo]
) -> dict[str, Any] | None:
    """End the turn as it stands, without asking the planner, when an agent's reply ended with
    choices for the author.

    The author answers them before anything else runs. An operation's result never ends the turn:
    the author never reads the operator's text.
    """
    # The result of a step that has just run, when the last message is one.
    just_ran = get_step_results(state["messages"][-1:])
    if not just_ran or just_ran[0].name == OPERATOR_AGENT_NAME:
        return None
    if _agent_reply_ends_with_choices(just_ran[0].artifact or ""):
        logger.info("Agent '%s' offered the author choices; the turn ends there", just_ran[0].name)
        return {"jump_to": "end"}
    return None
