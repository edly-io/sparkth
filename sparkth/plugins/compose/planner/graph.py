"""Building the planner: its prompt and its graph."""

from collections.abc import Sequence
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware
from langchain_core.language_models import BaseChatModel
from langgraph.graph.state import CompiledStateGraph

from sparkth.lib.audit.events import AuditModelInfo
from sparkth.lib.compose.constants import PLANNER_NAME
from sparkth.lib.compose.hooks import Agent
from sparkth.plugins.compose.constants import PLANNER_OPERATIONS, PLANNER_PROMPT, PLANNER_WITHOUT_OPERATIONS
from sparkth.plugins.compose.planner.middleware import first_hand_off_only, limit_steps
from sparkth.plugins.compose.planner.tools import REFUSE_TOOL, build_handoff_tool, build_operator_tool
from sparkth.plugins.compose.planner.types import AgentGraph


def render_planner_prompt(agents: Sequence[Agent], *, operations: bool) -> str:
    """The planner's system prompt, listing each of ``agents`` by its title and its description, and
    saying how to run operations when there are ``operations``, or what to do without them."""
    listed = "\n\n".join(f"## {agent.title}\n{agent.description}" for agent in agents)
    return PLANNER_PROMPT.format(
        agents=listed, operations=PLANNER_OPERATIONS if operations else PLANNER_WITHOUT_OPERATIONS
    )


def build_planner(
    llm: BaseChatModel,
    agents: Sequence[AgentGraph],
    *,
    operator: CompiledStateGraph[Any, AuditModelInfo, Any, Any] | None,
) -> CompiledStateGraph[Any, AuditModelInfo, Any, Any]:
    """Build the planner on ``llm``, with one hand-off tool per agent, the refuse tool, and the
    ``operator`` tool when there is an operator, which runs operations such as publishing a course.

    What a hand-off or an operation returns goes back to the planner, which runs the next step the
    author asked for or ends the turn. A turn runs a limited number of steps, a call its tool
    refuses goes back to the planner, and the agent that has just answered is not run again.

    The run's context is the :class:`AuditModelInfo` of the model the agents run on, which each
    hand-off passes on to its agent. A step, and each tool call inside it, waits for its reader to
    ask for the next event, so the planner must be streamed with ``stream_mode`` including
    ``"custom"`` and ``subgraphs=True``, and the reader must set the ``go`` of each ``routed`` and
    ``tool_start`` event.
    """
    # After-model hooks run in reverse order: a reply is trimmed to one call, then checked against the limits.
    middleware: list[AgentMiddleware[Any, Any, Any]] = [limit_steps, first_hand_off_only]
    operator_tools = [build_operator_tool(operator)] if operator is not None else []
    return create_agent(
        llm,
        [*(build_handoff_tool(agent) for agent in agents), *operator_tools, REFUSE_TOOL],
        system_prompt=render_planner_prompt([agent.spec for agent in agents], operations=operator is not None),
        middleware=middleware,
        context_schema=AuditModelInfo,
        name=PLANNER_NAME,
    )
