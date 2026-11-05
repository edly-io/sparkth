"""Building the planner: its prompt and its graph."""

from collections.abc import Sequence
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware
from langchain_core.language_models import BaseChatModel
from langgraph.graph.state import CompiledStateGraph

from sparkth.lib.audit.events import AuditModelInfo
from sparkth.lib.compose.hooks import Agent
from sparkth.plugins.compose.constants import PLANNER_OPERATIONS, PLANNER_PROMPT
from sparkth.plugins.compose.planner.middleware import (
    bounce_refused_calls,
    first_hand_off_only,
    stop_after_too_many_calls,
)
from sparkth.plugins.compose.planner.tools import REFUSE_TOOL, agent_handoff_tool, operator_tool
from sparkth.plugins.compose.planner.types import AgentGraph


def render_planner_prompt(agents: Sequence[Agent], *, operations: bool) -> str:
    """The planner's system prompt, listing each of ``agents`` by its title and its description, and
    saying how to run operations when there are ``operations``."""
    listed = "\n\n".join(f"## {agent.title}\n{agent.description}" for agent in agents)
    return PLANNER_PROMPT.format(agents=listed, operations=f"{PLANNER_OPERATIONS}\n" if operations else "")


def build_planner(
    llm: BaseChatModel,
    agents: Sequence[AgentGraph],
    *,
    operator: CompiledStateGraph[Any, AuditModelInfo, Any, Any] | None,
) -> CompiledStateGraph[Any, AuditModelInfo, Any, Any]:
    """Build the planner on ``llm``, with one hand-off tool per agent, the refuse tool, and the
    ``operator`` tool when there is an operator, which runs operations such as publishing a course.

    An operation's result goes back to the planner, so it can tell the author or hand the rest to
    an agent; a hand-off's result is the turn's answer.

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
    operator_tools = [operator_tool(operator)] if operator is not None else []
    return create_agent(
        llm,
        [*(agent_handoff_tool(agent) for agent in agents), *operator_tools, REFUSE_TOOL],
        system_prompt=render_planner_prompt([agent.spec for agent in agents], operations=operator is not None),
        middleware=middleware,
        context_schema=AuditModelInfo,
        name="compose",
    )
