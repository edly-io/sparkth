"""Types the planner builds on."""

from dataclasses import dataclass
from typing import Any

from langgraph.graph.state import CompiledStateGraph

from sparkth.lib.audit.events import AuditModelInfo
from sparkth.lib.compose.hooks import Agent


@dataclass(frozen=True)
class AgentGraph:
    """An enabled agent and the graph that runs it."""

    spec: Agent
    graph: CompiledStateGraph[Any, AuditModelInfo, Any, Any]


@dataclass(frozen=True)
class TurnRouting:
    """Who answered a turn: the agent it was handed to, if any, and whether it was refused."""

    agent: str | None = None
    refused: bool = False
