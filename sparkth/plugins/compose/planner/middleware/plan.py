"""Holding the planner to the plan the author was shown."""

from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware import AgentMiddleware, ToolCallRequest, wrap_tool_call
from langchain_core.messages import AIMessage, AnyMessage, ToolMessage
from langgraph.types import Command

from sparkth.lib.compose.constants import OPERATOR_AGENT_NAME, REFUSAL_TOOL_NAME, SHOW_PLAN_TOOL_NAME
from sparkth.lib.log import get_logger
from sparkth.plugins.compose.constants import (
    PLANNER_STEP_REQUEST,
    REJECT_MISSING_STEP_NUMBER,
    REJECT_OTHER_AGENTS_STEP,
    REJECT_PLAN_AFTER_A_STEP,
    REJECT_SECOND_PLAN,
    REJECT_STEP_AFTER_PLAN,
    REJECT_STEP_NOT_NEXT,
    REJECT_UNPLANNED_OPERATION,
)
from sparkth.plugins.compose.enums import TurnEventType
from sparkth.plugins.compose.planner.middleware.messages import get_shown_plan, get_step_number, get_step_results
from sparkth.plugins.compose.planner.middleware.types import Plan
from sparkth.plugins.compose.planner.types import ExistingPlan

logger = get_logger(__name__)

ToolCallHandler = Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]]


def _rejected_call(request: ToolCallRequest, reason: str) -> ToolMessage:
    """The result of the planner's ``request`` when it is rejected for ``reason``: the call never
    runs, and the planner reads the reason."""
    call = request.tool_call
    logger.warning("Planner's call to '%s' was rejected: %s", call["name"], reason)
    return ToolMessage(reason, tool_call_id=call["id"], name=call["name"], status="error")


def _get_first_step_number(messages: list[AnyMessage], pending_number: int | None) -> int | None:
    """The step number the turn's first step names: that of the first step that ran, or
    ``pending_number``, that of the call being checked, when none has run yet.

    It decides whether the turn carries on the existing plan.
    """
    step_results = get_step_results(messages)
    if not step_results:
        return pending_number
    calls = (call for message in messages if isinstance(message, AIMessage) for call in message.tool_calls)
    first = next(call for call in calls if call["id"] == step_results[0].tool_call_id)
    return get_step_number(first)


def get_plan(messages: list[AnyMessage], existing_plan: ExistingPlan | None, pending_number: int | None) -> Plan | None:
    """The plan the turn follows, if any: the one it showed, or ``existing_plan``, a plan from an
    earlier message, when its first step carries that on. ``pending_number`` is the step number of
    the call being checked."""
    step_results = get_step_results(messages)

    # No step runs before the turn's own plan is shown, so its next step is the count of steps run plus one.
    shown = get_shown_plan(messages)
    if shown is not None:
        return Plan(shown, (len(step_results) + 1,), from_earlier_message=False)

    # The existing plan is carried on only when the turn's first step names a step. A first step that
    # names none has dropped the plan for the whole turn.
    first = _get_first_step_number(messages, pending_number)
    if existing_plan is None or first is None:
        return None

    # Once carried on, its steps run in order from the first one the turn ran.
    if step_results:
        return Plan(existing_plan.steps, (first + len(step_results),), from_earlier_message=True)

    # A step that never ran, because the turn stopped at its limit before it or while it ran, runs next.
    current_step = existing_plan.current_step
    if not existing_plan.has_current_step_run:
        return Plan(existing_plan.steps, (current_step,), from_earlier_message=True)

    # An operation that ran is finished: it never waits for the author.
    if existing_plan.steps[current_step - 1].agent == OPERATOR_AGENT_NAME:
        return Plan(existing_plan.steps, (current_step + 1,), from_earlier_message=True)

    # An agent's step that ran may be finished or waiting for the author's answer, and only the planner
    # can tell, so that step or the one after it may run first.
    return Plan(existing_plan.steps, (current_step, current_step + 1), from_earlier_message=True)


def get_rejection_reason(tool_name: str, number: int, plan: Plan) -> str | None:
    """Why a call to ``tool_name`` for step ``number`` doesn't fit ``plan``, or None when it does:
    the step must be one that may run next, and the plan must have given it to this agent or the
    operator."""
    allowed_numbers = [allowed for allowed in plan.allowed_numbers if allowed <= len(plan.steps)]
    if not allowed_numbers:
        return REJECT_STEP_AFTER_PLAN
    if number not in allowed_numbers:
        following = " or ".join(str(allowed) for allowed in allowed_numbers)
        return REJECT_STEP_NOT_NEXT.format(step=number, next=following)
    if plan.steps[number - 1].agent != tool_name:
        return REJECT_OTHER_AGENTS_STEP.format(step=number)
    return None


async def _run_and_report_step(
    request: ToolCallRequest, handler: ToolCallHandler, step_number: int
) -> ToolMessage | Command[Any]:
    """Run the call for step ``step_number``, reporting the step on the stream as started, and as run
    once it has returned without an error."""
    request.runtime.stream_writer({"type": TurnEventType.PLAN_STEP, "number": step_number, "ran": False})
    result = await handler(request)
    if isinstance(result, ToolMessage) and result.status != "error":
        request.runtime.stream_writer({"type": TurnEventType.PLAN_STEP, "number": step_number, "ran": True})
    return result


def enforce_plan(existing_plan: ExistingPlan | None) -> AgentMiddleware[Any, Any, Any]:
    """Middleware that holds the planner to the plan shown to the author. Each of its calls is checked
    before it runs: one that fits the plan runs, and one that doesn't is rejected. ``existing_plan``
    is a plan from an earlier message that isn't finished.

    - A turn shows at most one plan, before its first step.
    - A turn continues the existing plan when its first step names one of that plan's steps. A first
      step that names none drops the existing plan for the whole turn.
    - With a plan, every hand-off and operation names the step it carries out. The steps run in
      order, each by the agent the plan gave it to.
    - Without a plan, an operation runs only as the turn's first step.
    - An operation is asked for its step's task as the author read it, not for what the planner
      wrote, when it follows another step or belongs to the existing plan.
    - An agent carrying out a step of a plan is told which step it is and its task, and to do only that step.
    - Each step of a plan is reported on the stream when it starts, and again once it has run.

    The rules about operations exist because what a step returned, an agent's reply or what an
    operation retrieved, can carry text from an uploaded document or the LMS, and the planner has
    read the existing plan's earlier steps too. That text must not be able to start an operation, or
    change what a planned one does. A hand-off is not restricted: an agent only writes for the
    author to read.
    """

    @wrap_tool_call(name="enforce_plan")
    async def check(request: ToolCallRequest, handler: ToolCallHandler) -> ToolMessage | Command[Any]:
        messages = request.state["messages"]
        call = request.tool_call
        tool_name = call["name"]
        step_results = get_step_results(messages)

        # Refusing the message has nothing to do with a plan.
        if tool_name == REFUSAL_TOOL_NAME:
            return await handler(request)

        # The plan is shown once, and before any step runs: after one, what that step returned could shape it.
        if tool_name == SHOW_PLAN_TOOL_NAME:
            if get_shown_plan(messages) is not None:
                return _rejected_call(request, REJECT_SECOND_PLAN)
            if step_results:
                return _rejected_call(request, REJECT_PLAN_AFTER_A_STEP)
            return await handler(request)

        # Without a plan every call runs, except an operation that follows another step.
        step_number = get_step_number(call)
        plan = get_plan(messages, existing_plan, step_number)
        if plan is None:
            if tool_name == OPERATOR_AGENT_NAME and step_results:
                return _rejected_call(request, REJECT_UNPLANNED_OPERATION)
            return await handler(request)

        # With a plan, the call must name a step that may run next, and the plan must have given that
        # step to this agent or the operator.
        if step_number is None:
            return _rejected_call(request, REJECT_MISSING_STEP_NUMBER)
        reason = get_rejection_reason(tool_name, step_number, plan)
        if reason is not None:
            return _rejected_call(request, reason)

        # An operation does what the plan said originally, not what the planner wrote after reading other steps.
        if tool_name == OPERATOR_AGENT_NAME and (plan.from_earlier_message or step_results):
            logger.info(
                "The operation for step %d is asked for the plan's task, not the planner's request", step_number
            )
            task = plan.steps[step_number - 1].task
            request = request.override(tool_call={**call, "args": {**call["args"], "request": task}})

        # An agent is told which step of the plan it is doing, so it leaves the other steps to their agents.
        elif tool_name != OPERATOR_AGENT_NAME:
            framed = PLANNER_STEP_REQUEST.format(
                number=step_number,
                total=len(plan.steps),
                task=plan.steps[step_number - 1].task,
                request=call["args"].get("request", ""),
            )
            request = request.override(tool_call={**call, "args": {**call["args"], "request": framed}})

        return await _run_and_report_step(request, handler, step_number)

    return check
