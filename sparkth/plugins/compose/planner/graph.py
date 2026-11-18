"""Building the planner: its prompt and its graph."""

from collections.abc import Sequence
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware
from langchain_core.language_models import BaseChatModel
from langgraph.graph.state import CompiledStateGraph

from sparkth.lib.audit.events import AuditModelInfo
from sparkth.lib.compose.constants import OPERATOR_AGENT_NAME, PLANNER_AGENT_NAME
from sparkth.lib.compose.hooks import Agent
from sparkth.lib.log import get_logger
from sparkth.plugins.compose.constants import (
    MAX_PLAN_STEPS,
    MAX_STEPS_PER_TURN,
    PLANNER_OPEN_PLAN,
    PLANNER_OPERATIONS,
    PLANNER_PROMPT,
    PLANNER_WITHOUT_OPERATIONS,
)
from sparkth.plugins.compose.planner.middleware import (
    enforce_plan,
    enforce_rejected_call_limit,
    enforce_step_limit,
    first_hand_off_only,
    no_repeat_hand_off,
    no_step_after_choices,
)
from sparkth.plugins.compose.planner.tools import (
    REFUSAL_TOOL,
    build_handoff_tool,
    build_operator_tool,
    show_plan_tool,
)
from sparkth.plugins.compose.planner.types import AgentGraph, OpenPlan

logger = get_logger(__name__)


def _drop_if_unrunnable(open_plan: OpenPlan | None, names: Sequence[str]) -> OpenPlan | None:
    """``open_plan`` when each of its steps from the one in progress onwards is for one of
    ``names``; a plan with a step none of them can do is dropped."""
    if open_plan is None:
        return None
    missing = {step.agent for step in open_plan.steps[open_plan.current - 1 :]} - set(names)
    if missing:
        logger.info("The unfinished plan is dropped: nobody in this turn does the steps of %s", sorted(missing))
        return None
    return open_plan


def _step_state(number: int, plan: OpenPlan) -> str:
    """Where step ``number`` of ``plan`` stands, as the planner reads it."""
    if number < plan.current:
        return "done"
    return "in progress" if number == plan.current else "not started"


def render_planner_prompt(agents: Sequence[Agent], *, operations: bool, open_plan: OpenPlan | None) -> str:
    """The planner's system prompt, listing each of ``agents`` by its title and its description,
    saying how to run operations when there are ``operations``, or what to do without them, giving
    the most steps a plan may have and a message may run, and ending with ``open_plan``, a plan from
    an earlier message that isn't finished, when there is one."""
    listed = "\n\n".join(f"## {agent.title}\n{agent.description}" for agent in agents)
    prompt = PLANNER_PROMPT.format(
        agents=listed,
        operations=PLANNER_OPERATIONS if operations else PLANNER_WITHOUT_OPERATIONS,
        max_steps=MAX_STEPS_PER_TURN,
        max_plan_steps=MAX_PLAN_STEPS,
    )
    if open_plan is None:
        return prompt
    steps = "\n".join(
        f"{number}. {step.task} ({step.agent}): {_step_state(number, open_plan)}"
        for number, step in enumerate(open_plan.steps, start=1)
    )
    return f"{prompt}\n\n{PLANNER_OPEN_PLAN.format(steps=steps)}"


def build_planner(
    llm: BaseChatModel,
    agents: Sequence[AgentGraph],
    *,
    operator: CompiledStateGraph[Any, AuditModelInfo, Any, Any] | None,
    open_plan: OpenPlan | None,
) -> CompiledStateGraph[Any, AuditModelInfo, Any, Any]:
    """Build the planner on ``llm``. It gives steps to ``agents``, and to ``operator`` when there is one.

    ``open_plan`` is a plan from an earlier message that isn't finished, which the turn may carry on.

    Stream it with ``stream_mode`` including ``"custom"`` and ``subgraphs=True``. Each step and tool
    call waits until the reader sets the ``go`` of its ``routed`` or ``tool_start`` event.
    """
    operator_tools = [build_operator_tool(operator)] if operator is not None else []
    names = [agent.spec.name for agent in agents] + ([OPERATOR_AGENT_NAME] if operator is not None else [])
    # Nobody to give a step to means nothing to plan.
    plan_tools = [show_plan_tool(names)] if names else []
    carried = _drop_if_unrunnable(open_plan, names)
    tools = [*(build_handoff_tool(agent) for agent in agents), *operator_tools, *plan_tools, REFUSAL_TOOL]
    # After-model hooks run in reverse order: a reply is trimmed to one call, checked against each limit,
    # then checked for a repeat hand-off. The before-model hook runs each time before the planner is asked.
    middleware: list[AgentMiddleware[Any, Any, Any]] = [
        no_step_after_choices,
        no_repeat_hand_off(carried),
        enforce_step_limit(carried),
        enforce_rejected_call_limit(carried),
        first_hand_off_only,
        enforce_plan(carried),
    ]
    return create_agent(
        llm,
        tools,
        system_prompt=render_planner_prompt(
            [agent.spec for agent in agents], operations=operator is not None, open_plan=carried
        ),
        middleware=middleware,
        context_schema=AuditModelInfo,
        name=PLANNER_AGENT_NAME,
    )
