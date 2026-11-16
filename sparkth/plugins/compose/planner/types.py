"""Types the planner builds on."""

from dataclasses import dataclass
from typing import Any

from langgraph.graph.state import CompiledStateGraph

from sparkth.lib.audit.events import AuditModelInfo
from sparkth.lib.compose.constants import OPERATOR_AGENT_NAME
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


@dataclass(frozen=True)
class OpenPlan:
    """A plan the author was shown that isn't finished: its steps, the number of the step it is at, and whether
    that step has run. A step that has run may be finished or waiting for the author; one that hasn't is next."""

    steps: tuple[PlannedStep, ...]
    current: int
    current_ran: bool

    @property
    def finished_count(self) -> int:
        """How many of its steps are known to be finished: those before the one it is at, and that one
        too when it is an operation that has run."""
        operated = self.current_ran and self.steps[self.current - 1].agent == OPERATOR_AGENT_NAME
        return self.current if operated else self.current - 1
