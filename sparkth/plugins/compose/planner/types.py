"""Types the planner builds on."""

from dataclasses import dataclass
from typing import Any

from langgraph.graph.state import CompiledStateGraph

from sparkth.lib.audit.events import AuditModelInfo
from sparkth.lib.compose.hooks import Agent
from sparkth.plugins.compose.constants import MAX_STEPS_PER_TURN


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
class ExistingPlan:
    """A plan the author was shown that isn't finished: its steps, and the number of the latest one that started."""

    steps: tuple[PlannedStep, ...]
    current: int

    def __post_init__(self) -> None:
        """Refuse a plan whose number of steps a plan can't have, or whose ``current`` isn't one of its steps."""
        if not 2 <= len(self.steps) <= MAX_STEPS_PER_TURN:
            raise ValueError(f"A plan has 2 to {MAX_STEPS_PER_TURN} steps, not {len(self.steps)}.")
        if not 1 <= self.current <= len(self.steps):
            raise ValueError(f"Step {self.current} is not one of the plan's {len(self.steps)} steps.")
