"""Building the planner: its prompt and its graph."""

from collections.abc import Sequence
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware
from langchain_core.language_models import BaseChatModel
from langgraph.graph.state import CompiledStateGraph

from sparkth.lib.audit.events import AuditModelInfo
from sparkth.lib.compose.constants import PLANNER_AGENT_NAME
from sparkth.lib.compose.hooks import Agent
from sparkth.plugins.compose.constants import PLANNER_OPERATIONS, PLANNER_PROMPT, PLANNER_WITHOUT_OPERATIONS
from sparkth.plugins.compose.enums import OptionsFence
from sparkth.plugins.compose.planner.middleware import (
    end_at_repeat_hand_off,
    end_turn_after_agent_offers_choices,
    enforce_rejected_call_limit,
    enforce_step_limit,
    first_hand_off_only,
)
from sparkth.plugins.compose.planner.tools import REFUSE_TOOL, build_handoff_tool, build_operator_tool
from sparkth.plugins.compose.planner.types import AgentGraph


def render_planner_prompt(agents: Sequence[Agent], *, operations: bool) -> str:
    """The planner's system prompt, listing each of ``agents`` by its title and its description, and
    saying how to run operations when there are ``operations``, or what to do without them."""
    listed = "\n\n".join(f"## {agent.title}\n{agent.description}" for agent in agents)
    return PLANNER_PROMPT.format(
        agents=listed,
        operations=PLANNER_OPERATIONS if operations else PLANNER_WITHOUT_OPERATIONS,
        options_tag=OptionsFence.MULTIPLE,
        single_options_tag=OptionsFence.SINGLE,
    )


def build_planner(
    llm: BaseChatModel,
    agents: Sequence[AgentGraph],
    *,
    operator: CompiledStateGraph[Any, AuditModelInfo, Any, Any] | None,
) -> CompiledStateGraph[Any, AuditModelInfo, Any, Any]:
    """Build the planner on ``llm``. It gives steps to ``agents``, and to ``operator`` when there is one.

    Stream it with ``stream_mode`` including ``"custom"`` and ``subgraphs=True``. Each step and tool
    call waits until the reader sets the ``go`` of its ``routed`` or ``tool_start`` event.
    """
    # After-model hooks run in reverse order: a reply is trimmed to one call, checked against each limit,
    # then checked for a repeat hand-off. The before-model hook runs each time before the planner is asked.
    middleware: list[AgentMiddleware[Any, Any, Any]] = [
        end_turn_after_agent_offers_choices,
        end_at_repeat_hand_off,
        enforce_step_limit,
        enforce_rejected_call_limit,
        first_hand_off_only,
    ]
    operator_tools = [build_operator_tool(operator)] if operator is not None else []
    return create_agent(
        llm,
        [*(build_handoff_tool(agent) for agent in agents), *operator_tools, REFUSE_TOOL],
        system_prompt=render_planner_prompt([agent.spec for agent in agents], operations=operator is not None),
        middleware=middleware,
        context_schema=AuditModelInfo,
        name=PLANNER_AGENT_NAME,
    )
