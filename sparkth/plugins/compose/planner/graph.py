"""Building the planner: its prompt and its graph."""

from collections.abc import Sequence
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware
from langchain_core.language_models import BaseChatModel
from langgraph.graph.state import CompiledStateGraph

from sparkth.lib.audit.events import AuditModelInfo
from sparkth.lib.compose.hooks import Agent
from sparkth.plugins.compose.constants import PLANNER_PROMPT
from sparkth.plugins.compose.planner.middleware import (
    bounce_refused_calls,
    first_hand_off_only,
    stop_after_too_many_calls,
)
from sparkth.plugins.compose.planner.tools import REFUSE_TOOL, agent_handoff_tool
from sparkth.plugins.compose.planner.types import AgentGraph


def render_planner_prompt(agents: Sequence[Agent]) -> str:
    """The planner's system prompt, listing each of ``agents`` by its title and its description."""
    listed = "\n\n".join(f"## {agent.title}\n{agent.description}" for agent in agents)
    return PLANNER_PROMPT.format(agents=listed)


def build_planner(
    llm: BaseChatModel, agents: Sequence[AgentGraph]
) -> CompiledStateGraph[Any, AuditModelInfo, Any, Any]:
    """Build the planner on ``llm``, with one hand-off tool per agent and the refuse tool.

    The run's context is the :class:`AuditModelInfo` of the model the agents run on, which each
    hand-off passes on to its agent. An agent's tool call waits for its reader to ask for the next
    event, so the planner must be streamed with ``stream_mode`` including ``"custom"`` and
    ``subgraphs=True``, and the reader must set each ``tool_start`` event's ``go``. A call its tool
    refuses goes back to the planner, and the run stops after a few calls (see
    :mod:`~sparkth.plugins.compose.planner.middleware`).
    """
    middleware: list[AgentMiddleware[Any, Any, Any]] = [
        first_hand_off_only,
        bounce_refused_calls,
        stop_after_too_many_calls,
    ]
    return create_agent(
        llm,
        [*(agent_handoff_tool(agent) for agent in agents), REFUSE_TOOL],
        system_prompt=render_planner_prompt([agent.spec for agent in agents]),
        middleware=middleware,
        context_schema=AuditModelInfo,
        name="compose",
    )
