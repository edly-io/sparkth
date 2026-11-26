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
    PLANNER_EXISTING_PLAN,
    PLANNER_OPERATIONS,
    PLANNER_PROMPT,
    PLANNER_WITHOUT_OPERATIONS,
)
from sparkth.plugins.compose.lib.enums import OptionsFence
from sparkth.plugins.compose.planner.middleware import (
    end_at_repeat_hand_off,
    end_turn_after_agent_offers_choices,
    enforce_plan,
    enforce_rejected_call_limit,
    enforce_step_limit,
    first_hand_off_only,
)
from sparkth.plugins.compose.planner.tools import (
    REFUSAL_TOOL,
    build_handoff_tool,
    build_operator_tool,
    show_plan_tool,
)
from sparkth.plugins.compose.planner.types import AgentGraph, ExistingPlan

logger = get_logger(__name__)


def _get_plan_or_none(existing_plan: ExistingPlan | None, agents: Sequence[str]) -> ExistingPlan | None:
    """``existing_plan``, or None when there is none or one of its steps from the one in progress
    onwards is for an agent that isn't in ``agents``."""
    if existing_plan is None:
        return None
    missing = {step.agent for step in existing_plan.steps[existing_plan.current_step - 1 :]} - set(agents)
    if missing:
        logger.info("The existing plan is dropped: no agent in this turn does the steps of %s", sorted(missing))
        return None
    return existing_plan


def _get_step_state(number: int, plan: ExistingPlan) -> str:
    """Where step ``number`` of ``plan`` stands, as the planner reads it: an operation that has run is done,
    an agent's step that has run is in progress, and one that hasn't run is next."""
    if number < plan.current_step:
        return "done"
    if number > plan.current_step:
        return "not started"
    if not plan.has_current_step_run:
        return "next"
    return "done" if plan.steps[number - 1].agent == OPERATOR_AGENT_NAME else "in progress"


def render_planner_prompt(agents: Sequence[Agent], *, operations: bool, existing_plan: ExistingPlan | None) -> str:
    """The planner's system prompt. It lists each of ``agents`` by title and description, says how to
    run operations when there are ``operations`` or what to do without them, gives the step limits for a
    plan and for a message, and ends with ``existing_plan`` when there is one."""
    listed = "\n\n".join(f"## {agent.title}\n{agent.description}" for agent in agents)
    prompt = PLANNER_PROMPT.format(
        agents=listed,
        operations=PLANNER_OPERATIONS if operations else PLANNER_WITHOUT_OPERATIONS,
        max_steps=MAX_STEPS_PER_TURN,
        max_plan_steps=MAX_PLAN_STEPS,
        options_tag=OptionsFence.MULTIPLE,
        single_options_tag=OptionsFence.SINGLE,
    )
    if existing_plan is not None:
        steps = "\n".join(
            f"{number}. {step.task} ({step.agent}): {_get_step_state(number, existing_plan)}"
            for number, step in enumerate(existing_plan.steps, start=1)
        )
        prompt = f"{prompt}\n\n{PLANNER_EXISTING_PLAN.format(steps=steps)}"
    return prompt


def build_planner(
    llm: BaseChatModel,
    agents: Sequence[AgentGraph],
    *,
    operator: CompiledStateGraph[Any, AuditModelInfo, Any, Any] | None,
    existing_plan: ExistingPlan | None,
) -> CompiledStateGraph[Any, AuditModelInfo, Any, Any]:
    """Build the planner on ``llm``. It gives steps to ``agents``, and to ``operator`` when there is one.

    ``existing_plan`` is a plan from an earlier message that isn't finished, which the turn may carry on.

    Stream it with ``stream_mode`` including ``"custom"`` and ``subgraphs=True``. Each step and tool
    call waits until the reader sets the ``go`` of its ``routed`` or ``tool_start`` event.
    """
    operator_tools = [build_operator_tool(operator)] if operator is not None else []
    agent_names = [agent.spec.name for agent in agents] + ([OPERATOR_AGENT_NAME] if operator is not None else [])
    # Nobody to give a step to means nothing to plan.
    plan_tools = [show_plan_tool(agent_names)] if agent_names else []
    existing_plan = _get_plan_or_none(existing_plan, agent_names)
    tools = [*(build_handoff_tool(agent) for agent in agents), *operator_tools, *plan_tools, REFUSAL_TOOL]
    # After-model hooks run in reverse order: a reply is trimmed to one call, checked against each limit,
    # then checked for a repeat hand-off. The before-model hook runs each time before the planner is asked.
    middleware: list[AgentMiddleware[Any, Any, Any]] = [
        end_turn_after_agent_offers_choices,
        end_at_repeat_hand_off(existing_plan),
        enforce_step_limit(existing_plan),
        enforce_rejected_call_limit(existing_plan),
        first_hand_off_only,
        enforce_plan(existing_plan),
    ]
    return create_agent(
        llm,
        tools,
        system_prompt=render_planner_prompt(
            [agent.spec for agent in agents], operations=operator is not None, existing_plan=existing_plan
        ),
        middleware=middleware,
        context_schema=AuditModelInfo,
        name=PLANNER_AGENT_NAME,
    )
