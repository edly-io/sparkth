"""The planner's middleware: one call per reply, calls checked against the plan, a limit on steps, a limit
on rejected calls, no repeat hand-off and no step after an agent's choices."""

from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware import AgentState, ToolCallRequest, after_model, before_model, wrap_tool_call
from langchain_core.messages import AIMessage, AnyMessage, ToolCall, ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import Command

from sparkth.lib.audit.events import AuditModelInfo
from sparkth.lib.compose.constants import OPERATOR_AGENT_NAME, REFUSAL_TOOL_NAME, SHOW_PLAN_TOOL_NAME
from sparkth.lib.i18n import gettext
from sparkth.lib.log import get_logger
from sparkth.plugins.compose.constants import (
    MAX_REJECTED_PLANNER_CALLS,
    MAX_STEPS_PER_TURN,
    REJECT_MISSING_STEP_NUMBER,
    REJECT_OTHER_AGENTS_STEP,
    REJECT_PLAN_AFTER_A_STEP,
    REJECT_SECOND_PLAN,
    REJECT_STEP_AFTER_PLAN,
    REJECT_STEP_NOT_NEXT,
    REJECT_UNPLANNED_OPERATION,
    STOPPED_EARLY_NOTICE,
)
from sparkth.plugins.compose.planner.types import PlannedStep

logger = get_logger(__name__)

# The lines that open a block of choices in a reply.
_CHOICES_FENCES = ("```options", "```options single")


def _step_results(messages: list[AnyMessage]) -> list[ToolMessage]:
    """The results of the steps the turn has run, each an agent's or the operator's work, in order.

    A call that was rejected ran nothing, and showing the plan or refusing the message is not a step.
    """
    return [
        message
        for message in messages
        if isinstance(message, ToolMessage)
        and message.status != "error"
        and message.name not in (SHOW_PLAN_TOOL_NAME, REFUSAL_TOOL_NAME)
    ]


def _shown_plan(messages: list[AnyMessage]) -> list[PlannedStep] | None:
    """The steps of the plan the author was shown in this turn, or None when no plan was shown."""
    # A plan that was rejected was never shown.
    plans: list[list[PlannedStep]] = [
        message.artifact
        for message in messages
        if isinstance(message, ToolMessage) and message.status != "error" and message.name == SHOW_PLAN_TOOL_NAME
    ]
    return plans[0] if plans else None


def _step_number(call: ToolCall) -> int | None:
    """The number of the plan step that ``call`` is for, or None when the call gives no whole number."""
    number = call["args"].get("step")
    # True is an int to Python, and would pass for step 1.
    return number if isinstance(number, int) and not isinstance(number, bool) else None


def _rejected_call(request: ToolCallRequest, reason: str) -> ToolMessage:
    """The result of the planner's ``request`` when it is rejected for ``reason``: the call never
    runs, and the planner reads the reason."""
    call = request.tool_call
    logger.warning("Planner's call to '%s' was rejected: %s", call["name"], reason)
    return ToolMessage(reason, tool_call_id=call["id"], name=call["name"], status="error")


@wrap_tool_call(name="enforce_plan")
async def enforce_plan(
    request: ToolCallRequest, handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]]
) -> ToolMessage | Command[Any]:
    """Hold the planner to the plan shown to the author. Each of its calls is checked before it runs:
    one that fits the plan runs, and one that doesn't is rejected.

    - A turn shows at most one plan, before its first step.
    - Once it has, every hand-off and operation names the step it carries out. The steps run in
      order, each by the agent the plan gave it to.
    - Without a plan, an operation runs only as the turn's first step.
    - An operation that follows another step is asked for its step's task as the author read it,
      not for what the planner wrote since.

    The last two rules exist because what a step returned, an agent's reply or what an operation
    retrieved, can carry text from an uploaded document or the LMS. That text must not be able to
    start an operation, or change what a planned one does. A hand-off is not restricted: an agent
    only writes for the author to read.
    """
    messages = request.state["messages"]
    call = request.tool_call
    tool_name = call["name"]
    step_results = _step_results(messages)
    plan = _shown_plan(messages)

    # Refusing the message has nothing to do with a plan.
    if tool_name == REFUSAL_TOOL_NAME:
        return await handler(request)

    # The plan is shown once, and before any step runs: after one, what that step returned could shape it.
    if tool_name == SHOW_PLAN_TOOL_NAME:
        if plan is not None:
            return _rejected_call(request, REJECT_SECOND_PLAN)
        if step_results:
            return _rejected_call(request, REJECT_PLAN_AFTER_A_STEP)
        return await handler(request)

    # Without a plan every call runs, except an operation that follows another step.
    if plan is None:
        if tool_name == OPERATOR_AGENT_NAME and step_results:
            return _rejected_call(request, REJECT_UNPLANNED_OPERATION)
        return await handler(request)

    # With a plan, the call must be for the next step, and the plan must have given that step to this
    # agent or the operator.
    next_step = len(step_results) + 1
    if next_step > len(plan):
        return _rejected_call(request, REJECT_STEP_AFTER_PLAN)
    step_number = _step_number(call)
    if step_number is None:
        return _rejected_call(request, REJECT_MISSING_STEP_NUMBER)
    if step_number != next_step:
        return _rejected_call(request, REJECT_STEP_NOT_NEXT.format(step=step_number, next=next_step))
    step = plan[step_number - 1]
    if step.agent != tool_name:
        return _rejected_call(request, REJECT_OTHER_AGENTS_STEP.format(step=step_number))

    # An operation that follows another step does what the plan said originally, not what the planner wrote since.
    if tool_name == OPERATOR_AGENT_NAME and step_results:
        logger.info("The operation for step %d is asked for the plan's task, not the planner's request", step_number)
        request = request.override(tool_call={**call, "args": {**call["args"], "request": step.task}})
    return await handler(request)


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


@after_model(can_jump_to=["end"], name="enforce_rejected_call_limit")
def enforce_rejected_call_limit(state: AgentState[Any], runtime: Runtime[AuditModelInfo]) -> dict[str, Any] | None:
    """End the turn, telling the author it could not finish, when the planner asks for another call
    after more of its calls were rejected than a turn allows. A call is rejected when it names no
    tool the planner has, its arguments don't fit the tool, or it doesn't fit the plan. Nothing ran,
    so it is not a step, and a planner that fixes its call still gets to finish the turn."""
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


@after_model(name="no_repeat_hand_off")
def no_repeat_hand_off(state: AgentState[Any], runtime: Runtime[AuditModelInfo]) -> dict[str, Any] | None:
    """End the turn as it stands when the planner hands off again to the agent that has just answered.

    The author has just read that agent's reply, often a question for them. The operator may run
    twice in a row: the author never reads its text. A turn with a plan is left alone: there the
    same agent may do two steps in a row.
    """
    reply = state["messages"][-1]
    if not (isinstance(reply, AIMessage) and reply.tool_calls):
        return None
    if _shown_plan(state["messages"]) is not None:
        return None
    step_results = _step_results(state["messages"])
    next_agent = reply.tool_calls[0]["name"]
    if next_agent != OPERATOR_AGENT_NAME and step_results and step_results[-1].name == next_agent:
        logger.warning("Planner handed off to '%s' again right after its reply; the turn ends there", next_agent)
        return {"messages": [_with_calls(reply, [])]}
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
