"""Reading the planner's conversation, and trimming its replies, for the planner's middleware."""

from typing import Any

from langchain_core.messages import AIMessage, AnyMessage, ToolCall, ToolMessage

from sparkth.lib.compose.constants import REFUSAL_TOOL_NAME, SHOW_PLAN_TOOL_NAME
from sparkth.plugins.compose.planner.types import PlannedStep


def get_step_results(messages: list[AnyMessage]) -> list[ToolMessage]:
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


def get_shown_plan(messages: list[AnyMessage]) -> list[PlannedStep] | None:
    """The steps of the plan the author was shown in this turn, or None when no plan was shown."""
    # A plan that was rejected was never shown.
    plans: list[list[PlannedStep]] = [
        message.artifact
        for message in messages
        if isinstance(message, ToolMessage) and message.status != "error" and message.name == SHOW_PLAN_TOOL_NAME
    ]
    return plans[0] if plans else None


def get_step_number(call: ToolCall) -> int | None:
    """The number of the plan step that ``call`` is for, or None when the call gives no whole number."""
    number = call["args"].get("step")
    # True is an int to Python, and would pass for step 1.
    return number if isinstance(number, int) and not isinstance(number, bool) else None


def with_calls(reply: AIMessage, kept: list[ToolCall]) -> AIMessage:
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
