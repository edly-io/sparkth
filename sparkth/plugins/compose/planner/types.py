"""Types the planner builds on."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from langchain_core.language_models import BaseChatModel
from langgraph.graph.state import CompiledStateGraph

from sparkth.lib.audit.events import AuditModelInfo
from sparkth.lib.compose.hooks import Agent
from sparkth.plugins.compose.constants import MAX_PLAN_STEPS


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
    """A plan the author was shown that isn't finished: its steps, the number of the step it is at, the
    latest that started or the next when the turn stopped at its limit of steps, and whether that step
    has run."""

    steps: tuple[PlannedStep, ...]
    current_step: int
    has_current_step_run: bool = True

    def __post_init__(self) -> None:
        """Refuse a plan whose number of steps a plan can't have, or whose ``current_step`` isn't one of its steps."""
        if not 2 <= len(self.steps) <= MAX_PLAN_STEPS:
            raise ValueError(f"A plan can have 2 to {MAX_PLAN_STEPS} steps, not {len(self.steps)}.")
        if not 1 <= self.current_step <= len(self.steps):
            raise ValueError(f"Step {self.current_step} is not one of the plan's {len(self.steps)} steps.")


@dataclass(frozen=True)
class PlanSnapshot:
    """A plan as the author sees it: its tasks, the number of the step it is at (0 before the first starts),
    and whether that step has run."""

    tasks: tuple[str, ...]
    current_step: int
    has_current_step_run: bool


@dataclass(frozen=True)
class PlannerSetup:
    """Inputs for building the planner for one turn.

    Attributes:
        agents: Agents the planner can hand the message to.
        planner_llm: Model the planner runs on.
        existing_plan: The plan saved with the latest reply, for this turn to carry on, or None.
    """

    agents: Sequence[Agent]
    planner_llm: BaseChatModel
    existing_plan: ExistingPlan | None
