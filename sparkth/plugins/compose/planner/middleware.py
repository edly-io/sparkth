"""The planner's middleware: one call per reply, calls checked against the plan, a limit on steps, a limit
on rejected calls, no repeat hand-off and no step after an agent's choices."""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any

from langchain.agents.middleware import (
    AgentMiddleware,
    AgentState,
    ToolCallRequest,
    after_model,
    before_model,
    wrap_tool_call,
)
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
    PLAN_CONTINUE_CHOICE,
    PLAN_CONTINUE_QUESTION,
    PLAN_DONE_HEADING,
    PLAN_LEFT_HEADING,
    PLAN_PAUSED_NOTE,
    PLAN_STOP_CHOICE,
    REJECT_MISSING_STEP_NUMBER,
    REJECT_OTHER_AGENTS_STEP,
    REJECT_PLAN_AFTER_A_STEP,
    REJECT_SECOND_PLAN,
    REJECT_STEP_AFTER_PLAN,
    REJECT_STEP_NOT_NEXT,
    REJECT_UNPLANNED_OPERATION,
    STOPPED_EARLY_NOTICE,
)
from sparkth.plugins.compose.enums import OptionsFence, TurnEventType
from sparkth.plugins.compose.planner.types import OpenPlan, PlannedStep

logger = get_logger(__name__)

# The lines that open a block of choices in a reply.
_CHOICES_FENCES = tuple(f"```{fence}" for fence in OptionsFence)


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


@dataclass(frozen=True)
class _ActivePlan:
    """The plan a turn follows: its steps, the numbers of the steps that may run next, and whether
    it was carried on from an earlier message."""

    steps: Sequence[PlannedStep]
    allowed_numbers: tuple[int, ...]
    from_earlier_message: bool


def _first_call_number(messages: list[AnyMessage], pending_number: int | None) -> int | None:
    """The step number of the call that decides whether the turn carries on an earlier plan: the
    turn's first step that ran, or the call it is ``pending_number`` for now when none has run."""
    step_results = _step_results(messages)
    if not step_results:
        return pending_number
    calls = (call for message in messages if isinstance(message, AIMessage) for call in message.tool_calls)
    first = next(call for call in calls if call["id"] == step_results[0].tool_call_id)
    return _step_number(first)


def _active_plan(
    messages: list[AnyMessage], open_plan: OpenPlan | None, pending_number: int | None
) -> _ActivePlan | None:
    """The plan the turn follows, if any: the one it showed, or ``open_plan``, a plan from an earlier
    message, when its first step carries that on. ``pending_number`` is the step number of the call being
    checked."""
    step_results = _step_results(messages)

    # No step runs before the turn's own plan is shown, so its next step is the count of steps run plus one.
    shown = _shown_plan(messages)
    if shown is not None:
        return _ActivePlan(shown, (len(step_results) + 1,), from_earlier_message=False)

    # An earlier plan is carried on only when the turn's first step names a step. A first step that
    # names none has dropped the plan for the whole turn.
    first = _first_call_number(messages, pending_number)
    if open_plan is None or first is None:
        return None

    # Once carried on, its steps run in order from the first one the turn ran.
    if step_results:
        return _ActivePlan(open_plan.steps, (first + len(step_results),), from_earlier_message=True)

    # A step that hasn't run is next: it waited at the turn's limit, or failed or was stopped.
    if not open_plan.current_ran:
        return _ActivePlan(open_plan.steps, (open_plan.current,), from_earlier_message=True)

    # An operation that has run is done, so only the step after it may run.
    if open_plan.finished_count == open_plan.current:
        return _ActivePlan(open_plan.steps, (open_plan.current + 1,), from_earlier_message=True)

    # An agent's step that has run may be finished or waiting for the author, and only the planner
    # can tell, so that step or the one after it may run first.
    return _ActivePlan(open_plan.steps, (open_plan.current, open_plan.current + 1), from_earlier_message=True)


def _why_rejected(tool_name: str, number: int, plan: _ActivePlan) -> str | None:
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


def enforce_plan(open_plan: OpenPlan | None) -> AgentMiddleware[Any, Any, Any]:
    """Middleware that holds the planner to the plan shown to the author. Each of its calls is checked
    before it runs: one that fits the plan runs, and one that doesn't is rejected. ``open_plan`` is a
    plan from an earlier message that isn't finished.

    - A turn shows at most one plan, before its first step.
    - A turn continues the open plan when its first step names one of that plan's steps. A first
      step that names none drops the open plan for the whole turn.
    - With a plan, every hand-off and operation names the step it carries out. The steps run in
      order, each by the agent the plan gave it to.
    - Without a plan, an operation runs only as the turn's first step.
    - An operation is asked for its step's task as the author read it, not for what the planner
      wrote, when it follows another step or belongs to the open plan.
    - Each step of a plan is reported on the stream when it starts, and again once it has run.

    The rules about operations exist because what a step returned, an agent's reply or what an
    operation retrieved, can carry text from an uploaded document or the LMS, and the planner has
    read the open plan's earlier steps too. That text must not be able to start an operation, or
    change what a planned one does. A hand-off is not restricted: an agent only writes for the
    author to read.
    """

    @wrap_tool_call(name="enforce_plan")
    async def check(
        request: ToolCallRequest, handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]]
    ) -> ToolMessage | Command[Any]:
        messages = request.state["messages"]
        call = request.tool_call
        tool_name = call["name"]
        step_results = _step_results(messages)

        # Refusing the message has nothing to do with a plan.
        if tool_name == REFUSAL_TOOL_NAME:
            return await handler(request)

        # The plan is shown once, and before any step runs: after one, what that step returned could shape it.
        if tool_name == SHOW_PLAN_TOOL_NAME:
            if _shown_plan(messages) is not None:
                return _rejected_call(request, REJECT_SECOND_PLAN)
            if step_results:
                return _rejected_call(request, REJECT_PLAN_AFTER_A_STEP)
            return await handler(request)

        # Without a plan every call runs, except an operation that follows another step.
        step_number = _step_number(call)
        plan = _active_plan(messages, open_plan, step_number)
        if plan is None:
            if tool_name == OPERATOR_AGENT_NAME and step_results:
                return _rejected_call(request, REJECT_UNPLANNED_OPERATION)
            return await handler(request)

        # With a plan, the call must name a step that may run next, and the plan must have given that
        # step to this agent or the operator.
        if step_number is None:
            return _rejected_call(request, REJECT_MISSING_STEP_NUMBER)
        reason = _why_rejected(tool_name, step_number, plan)
        if reason is not None:
            return _rejected_call(request, reason)

        # An operation does what the plan said originally, not what the planner wrote after reading other steps.
        if tool_name == OPERATOR_AGENT_NAME and (plan.from_earlier_message or step_results):
            logger.info(
                "The operation for step %d is asked for the plan's task, not the planner's request", step_number
            )
            task = plan.steps[step_number - 1].task
            request = request.override(tool_call={**call, "args": {**call["args"], "request": task}})

        # Report the step as started, and as run once it has returned without an error.
        report = request.runtime.stream_writer
        report({"type": TurnEventType.PLAN_STEP, "number": step_number, "ran": False})
        result = await handler(request)
        if isinstance(result, ToolMessage) and result.status != "error":
            report({"type": TurnEventType.PLAN_STEP, "number": step_number, "ran": True})
        return result

    return check


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


def _paused_plan_message(steps: Sequence[PlannedStep], done: int) -> str:
    """What the author reads when a turn stops at its limit with steps of its plan left: the first
    ``done`` tasks as done, the rest as left, and the choice to carry on or stop."""
    tasks = [f"{number}. {step.task}" for number, step in enumerate(steps, start=1)]
    choices = [f"```{OptionsFence.SINGLE}", gettext(PLAN_CONTINUE_CHOICE), gettext(PLAN_STOP_CHOICE), "```"]
    # A blank line after each heading: a numbered list that doesn't start at 1 can't follow a line of text.
    return "\n\n".join(
        [
            gettext(PLAN_PAUSED_NOTE),
            gettext(PLAN_DONE_HEADING),
            "\n".join(tasks[:done]),
            gettext(PLAN_LEFT_HEADING),
            "\n".join(tasks[done:]),
            "\n".join([gettext(PLAN_CONTINUE_QUESTION), *choices]),
        ]
    )


def _turn_ending(
    messages: list[AnyMessage],
    reply: AIMessage,
    open_plan: OpenPlan | None,
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
    number = _step_number(call)
    plan = _active_plan(messages, open_plan, number)
    if plan is not None and number is not None and _step_results(messages):
        if _why_rejected(call["name"], number, plan) is None:
            runtime.stream_writer({"type": TurnEventType.PLAN_STEP, "number": number, "ran": False})
            return {"jump_to": "end", "messages": [AIMessage(content=_paused_plan_message(plan.steps, number - 1))]}
    return {"jump_to": "end", "messages": [AIMessage(content=notice)]}


def enforce_step_limit(open_plan: OpenPlan | None) -> AgentMiddleware[Any, Any, Any]:
    """Middleware that ends the turn when the planner asks for another call after the turn's max
    number of steps has run. ``open_plan`` is a plan from an earlier message that isn't finished."""

    @after_model(can_jump_to=["end"], name="enforce_step_limit")
    def end_at_the_step_limit(state: AgentState[Any], runtime: Runtime[AuditModelInfo]) -> dict[str, Any] | None:
        messages = state["messages"]
        reply = messages[-1]
        if not (isinstance(reply, AIMessage) and reply.tool_calls):
            return None
        steps_run = len(_step_results(messages))
        if steps_run < MAX_STEPS_PER_TURN:
            return None
        logger.warning(
            "Planner asked for another call after %d steps (limit %d); the turn ends there",
            steps_run,
            MAX_STEPS_PER_TURN,
        )
        return _turn_ending(messages, reply, open_plan, runtime, gettext(STOPPED_EARLY_NOTICE))

    return end_at_the_step_limit


def enforce_rejected_call_limit(open_plan: OpenPlan | None) -> AgentMiddleware[Any, Any, Any]:
    """Middleware that ends the turn when the planner asks for another call after more of its calls
    were rejected than a turn allows. ``open_plan`` is a plan from an earlier message that isn't
    finished.

    A call is rejected when it names no tool the planner has, its arguments don't fit the tool, or
    it doesn't fit the plan. Nothing ran, so it is not a step, and a planner that fixes its call
    still gets to finish the turn.
    """

    @after_model(can_jump_to=["end"], name="enforce_rejected_call_limit")
    def end_at_the_rejected_call_limit(
        state: AgentState[Any], runtime: Runtime[AuditModelInfo]
    ) -> dict[str, Any] | None:
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
        return _turn_ending(messages, reply, open_plan, runtime, could_not_finish)

    return end_at_the_rejected_call_limit


def no_repeat_hand_off(open_plan: OpenPlan | None) -> AgentMiddleware[Any, Any, Any]:
    """Middleware that ends the turn as it stands when the planner hands off again to the agent that
    has just answered. ``open_plan`` is a plan from an earlier message that isn't finished.

    The author has just read that agent's reply, often a question for them. The operator may run
    twice in a row: the author never reads its text. A turn that follows a plan is left alone: there
    the same agent may do two steps in a row.
    """

    @after_model(name="no_repeat_hand_off")
    def end_on_a_repeat(state: AgentState[Any], runtime: Runtime[AuditModelInfo]) -> dict[str, Any] | None:
        messages = state["messages"]
        reply = messages[-1]
        if not (isinstance(reply, AIMessage) and reply.tool_calls):
            return None
        call = reply.tool_calls[0]
        if _active_plan(messages, open_plan, _step_number(call)) is not None:
            return None
        step_results = _step_results(messages)
        next_agent = call["name"]
        if next_agent != OPERATOR_AGENT_NAME and step_results and step_results[-1].name == next_agent:
            logger.warning("Planner handed off to '%s' again right after its reply; the turn ends there", next_agent)
            return {"messages": [_with_calls(reply, [])]}
        return None

    return end_on_a_repeat


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
