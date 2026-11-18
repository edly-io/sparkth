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
    """Who answered a turn: the agent it was handed to or the operator, if any, and whether it was refused."""

    agent: str | None = None
    refused: bool = False


@dataclass(frozen=True)
class PlannedStep:
    """One step of the planner's plan: the agent or operator that does it, and the task the author reads."""

    agent: str
    task: str
